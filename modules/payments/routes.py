"""
Payment Management and Salary Slips routes (Module 7).
Handles:
- Viewing approved payroll records awaiting disbursement.
- Recording payment transactions (bank transfer, cheque, cash, UPI, direct deposit).
- Payment ledger with search, filtering, and summary metrics in INR.
- Viewing payment vouchers and handling controlled status transitions (e.g., reversal).
- Printable HTML salary slip statements.
- PDF salary slip generation and download.
- Academic simulation disclaimers (no real money transferred).
"""

from datetime import date
import io
import math
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    jsonify,
    abort,
)
from modules.auth.services import login_required
from modules.payments.services import (
    PaymentService,
    PaymentProcessingError,
    DuplicatePaymentReferenceError,
    InvalidPaymentAmountError,
    IneligiblePayrollError,
    InvalidPaymentStatusTransitionError,
    PAYMENT_METHODS,
)
from modules.attendance.validators import MONTH_NAMES

MONTH_DICT = {i: MONTH_NAMES[i] for i in range(1, 13)}

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")
service = PaymentService()


@payments_bp.route("")
@payments_bp.route("/")
@login_required
def index():
    """
    Paginated payment vouchers ledger with filters for period, status, method,
    search toolbar, and summary disbursement metrics in INR.
    """
    search_query = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "ALL").strip().upper()
    method_filter = request.args.get("method", "ALL").strip().upper()

    raw_year = request.args.get("year", "").strip()
    raw_month = request.args.get("month", "").strip()

    selected_year = int(raw_year) if raw_year and raw_year.isdigit() else None
    selected_month = int(raw_month) if raw_month and raw_month.isdigit() else None

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    per_page = 10
    payments_list, total_count = service.get_payment_history(
        year=selected_year,
        month=selected_month,
        status=status_filter if status_filter != "ALL" else None,
        method=method_filter if method_filter != "ALL" else None,
        search=search_query or None,
        page=page,
        per_page=per_page,
    )

    total_pages = max(1, math.ceil(total_count / per_page))

    # Aggregated summary metrics for filtered period
    summary = service.payment_repo.get_payment_summary(year=selected_year, month=selected_month)

    # Count of approved payrolls awaiting payment
    awaiting_list = service.get_awaiting_payroll_records()
    awaiting_count = len(awaiting_list)

    available_years = service.payment_repo.get_available_years()

    return render_template(
        "payments/index.html",
        payments=payments_list,
        page=page,
        per_page=per_page,
        total_count=total_count,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
        search_query=search_query,
        status_filter=status_filter,
        method_filter=method_filter,
        selected_year=selected_year,
        selected_month=selected_month,
        summary=summary,
        awaiting_count=awaiting_count,
        available_years=available_years,
        month_names=MONTH_DICT,
        payment_methods=PAYMENT_METHODS,
    )


@payments_bp.route("/awaiting")
@login_required
def awaiting():
    """
    List of approved payroll statements awaiting payment disbursement.
    """
    raw_year = request.args.get("year", "").strip()
    raw_month = request.args.get("month", "").strip()

    selected_year = int(raw_year) if raw_year and raw_year.isdigit() else None
    selected_month = int(raw_month) if raw_month and raw_month.isdigit() else None

    records = service.get_awaiting_payroll_records(year=selected_year, month=selected_month)
    available_years = service.payment_repo.get_available_years()

    return render_template(
        "payments/awaiting.html",
        records=records,
        selected_year=selected_year,
        selected_month=selected_month,
        available_years=available_years,
        month_names=MONTH_DICT,
    )


@payments_bp.route("/record/<int:payroll_id>", methods=["GET", "POST"])
@login_required
def record_payment(payroll_id: int):
    """
    Record payment details for an approved payroll record.
    Academic simulation notice is displayed to make clear no real money is transferred.
    """
    payroll = service.payroll_repo.get_by_id(payroll_id)
    if not payroll:
        flash(f"Payroll record #{payroll_id} was not found.", "warning")
        return redirect(url_for("payments.index"))

    if request.method == "POST":
        payment_date = request.form.get("payment_date") or date.today()
        amount = request.form.get("amount")
        payment_method = request.form.get("payment_method", "BANK_TRANSFER")
        payment_reference = request.form.get("payment_reference", "")
        status = request.form.get("status", "SUCCESSFUL")
        transaction_notes = request.form.get("transaction_notes", "")

        try:
            payment_id = service.record_payment(
                payroll_id=payroll_id,
                payment_date=payment_date,
                amount=amount,
                payment_method=payment_method,
                payment_reference=payment_reference,
                status=status,
                transaction_notes=transaction_notes,
            )
            flash(
                f"Payment recorded successfully ({payment_method}). "
                f"Payroll {payroll['payroll_code']} marked as {('PAID' if status == 'SUCCESSFUL' else payroll['status'])}.",
                "success",
            )
            return redirect(url_for("payments.view", payment_id=payment_id))
        except (InvalidPaymentAmountError, DuplicatePaymentReferenceError, IneligiblePayrollError, PaymentProcessingError) as err:
            flash(f"Payment failed: {str(err)}", "danger")
            return redirect(url_for("payments.record_payment", payroll_id=payroll_id))
        except Exception as err:
            flash(f"Unexpected error processing payment: {str(err)}", "danger")
            return redirect(url_for("payments.record_payment", payroll_id=payroll_id))

    # GET Request: Generate default reference
    default_reference = service.payment_repo.generate_payment_reference("BANK_TRANSFER", payroll["payroll_code"])

    return render_template(
        "payments/record.html",
        payroll=payroll,
        default_reference=default_reference,
        payment_methods=PAYMENT_METHODS,
        today=date.today().isoformat(),
        month_names=MONTH_DICT,
    )


@payments_bp.route("/<int:payment_id>")
@login_required
def view(payment_id: int):
    """
    View payment transaction voucher and audit trail details.
    """
    payment = service.get_payment_details(payment_id)
    if not payment:
        flash(f"Payment voucher #{payment_id} was not found.", "warning")
        return redirect(url_for("payments.index"))

    return render_template(
        "payments/view.html",
        payment=payment,
        month_names=MONTH_DICT,
    )


@payments_bp.route("/<int:payment_id>/status", methods=["POST"])
@login_required
def update_status(payment_id: int):
    """
    Controlled payment status transitions:
    - reverse: SUCCESSFUL -> REVERSED (rolls back associated payroll to APPROVED)
    - confirm: PENDING -> SUCCESSFUL (marks payroll as PAID)
    - fail: PENDING -> FAILED
    """
    action = request.form.get("action", "").lower().strip()
    reason = request.form.get("reason", "").strip() or None

    target_map = {
        "reverse": "REVERSED",
        "confirm": "SUCCESSFUL",
        "fail": "FAILED",
    }

    if action not in target_map:
        flash("Invalid payment action requested.", "danger")
        return redirect(url_for("payments.view", payment_id=payment_id))

    target_status = target_map[action]

    success, message = service.transition_payment_status(
        payment_id=payment_id, target_status=target_status, reason=reason
    )
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for("payments.view", payment_id=payment_id))


@payments_bp.route("/slip/<int:payroll_id>")
@login_required
def salary_slip(payroll_id: int):
    """
    Printable salary slip view (HTML format with print CSS).
    """
    try:
        slip_data = service.get_salary_slip_data(payroll_id)
    except PaymentProcessingError as err:
        flash(str(err), "warning")
        return redirect(url_for("payments.index"))

    return render_template(
        "payments/slip.html",
        slip=slip_data,
        payroll=slip_data["payroll"],
        employee=slip_data["employee"],
        attendance=slip_data["attendance"],
        payment=slip_data["payment"],
        month_name=slip_data["month_name"],
        year=slip_data["year"],
    )


@payments_bp.route("/slip/<int:payroll_id>/pdf")
@login_required
def download_slip_pdf(payroll_id: int):
    """
    Generate and download salary slip as PDF using ReportLab.
    """
    try:
        pdf_bytes = service.generate_salary_slip_pdf(payroll_id)
        payroll = service.payroll_repo.get_by_id(payroll_id)
        filename = f"SalarySlip_{payroll['payroll_code']}.pdf" if payroll else f"SalarySlip_{payroll_id}.pdf"

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as err:
        logger.error("Error generating salary slip PDF for payroll #%s: %s", payroll_id, err)
        flash(f"Could not generate PDF salary slip: {str(err)}. Rendering print-friendly HTML version.", "warning")
        return redirect(url_for("payments.salary_slip", payroll_id=payroll_id))
