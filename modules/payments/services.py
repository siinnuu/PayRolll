"""
Payment Management and Salary Slips Service Layer (Module 7).
Handles:
- Processing and recording payments for approved payroll statements.
- Duplicate transaction reference validation.
- Concurrency safeguards and transactional status synchronization.
- Controlled payment status reversals and corrections.
- Salary slip data preparation.
- Production-grade PDF salary slip generation via ReportLab.
- Academic simulation disclaimers (no real money transferred).
"""

from datetime import date
from decimal import Decimal, InvalidOperation
import io
import logging
from typing import Any, Dict, List, Optional, Tuple

from repositories.payment_repository import PaymentRepository
from repositories.payroll_repository import PayrollRepository
from repositories.employee_repository import EmployeeRepository
from repositories.attendance_repository import AttendanceRepository
from repositories.salary_repository import SalaryRepository
from modules.attendance.validators import MONTH_NAMES

logger = logging.getLogger(__name__)

# Allowed disbursement payment methods
PAYMENT_METHODS = ["BANK_TRANSFER", "CASH", "CHEQUE", "UPI", "DIRECT_DEPOSIT"]


class PaymentProcessingError(Exception):
    """Base exception for payment disbursement and validation failures."""
    pass


class DuplicatePaymentReferenceError(PaymentProcessingError):
    """Raised when an attempt is made to use an already existing payment reference."""
    pass


class InvalidPaymentAmountError(PaymentProcessingError):
    """Raised when payment amount is negative, zero, non-numeric, or mismatches payroll."""
    pass


class IneligiblePayrollError(PaymentProcessingError):
    """Raised when payroll statement is not approved or is already paid."""
    pass


class InvalidPaymentStatusTransitionError(PaymentProcessingError):
    """Raised when an invalid payment status transition is attempted."""
    pass


class PaymentService:
    """Business service coordinating payment execution, status lifecycles, and payslip generation."""

    def __init__(
        self,
        payment_repo: Optional[PaymentRepository] = None,
        payroll_repo: Optional[PayrollRepository] = None,
        employee_repo: Optional[EmployeeRepository] = None,
        attendance_repo: Optional[AttendanceRepository] = None,
        salary_repo: Optional[SalaryRepository] = None,
    ):
        self.payment_repo = payment_repo or PaymentRepository()
        self.payroll_repo = payroll_repo or PayrollRepository()
        self.employee_repo = employee_repo or EmployeeRepository()
        self.attendance_repo = attendance_repo or AttendanceRepository()
        self.salary_repo = salary_repo or SalaryRepository()

    def get_awaiting_payroll_records(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch approved payroll records awaiting disbursement."""
        return self.payment_repo.get_approved_payrolls_awaiting_payment(year=year, month=month)

    def get_payment_history(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        status: Optional[str] = None,
        method: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch paginated payment vouchers."""
        return self.payment_repo.get_paginated_payments(
            year=year,
            month=month,
            status=status,
            method=method,
            search=search,
            page=page,
            per_page=per_page,
        )

    def get_payment_details(self, payment_id: int) -> Optional[Dict[str, Any]]:
        """Fetch complete payment disbursement details."""
        return self.payment_repo.get_by_id(payment_id)

    def record_payment(
        self,
        payroll_id: int,
        payment_date: Any,
        amount: Any,
        payment_method: str,
        payment_reference: str,
        status: str = "SUCCESSFUL",
        transaction_notes: Optional[str] = None,
    ) -> int:
        """
        Record a payment transaction for an approved payroll record.
        Wraps operations in an ACID database transaction.
        
        Rules:
        - Academic application disclaimer: no real money is transferred.
        - Payroll must be in APPROVED status.
        - Amount must be positive Decimal equal to payroll net_pay.
        - Payment reference must be unique.
        - Payment method must be one of PAYMENT_METHODS.
        - If status == 'SUCCESSFUL': payroll status is updated to 'PAID'.
        - If status != 'SUCCESSFUL': payroll status is NOT updated to 'PAID'.
        """
        # 1. Fetch and verify payroll record
        payroll = self.payroll_repo.get_by_id(payroll_id)
        if not payroll:
            raise IneligiblePayrollError(f"Payroll statement #{payroll_id} was not found.")

        current_payroll_status = payroll["status"].upper()
        if current_payroll_status == "PAID":
            raise IneligiblePayrollError(
                f"Payroll statement {payroll['payroll_code']} has already been PAID. "
                "Repeated payment attempts for the same payroll record are strictly prevented."
            )
        elif current_payroll_status != "APPROVED":
            raise IneligiblePayrollError(
                f"Payroll statement {payroll['payroll_code']} is in '{current_payroll_status}' status. "
                "Only statements in 'APPROVED' status are eligible for payment disbursement."
            )

        # 2. Check for existing successful payment linked to this payroll
        existing_pm = self.payment_repo.get_by_payroll_id(payroll_id)
        if existing_pm and existing_pm["status"].upper() == "SUCCESSFUL":
            raise IneligiblePayrollError(
                f"A confirmed payment voucher ({existing_pm['payment_reference']}) already exists for this payroll."
            )

        # 3. Validate payment amount
        try:
            amount_decimal = Decimal(str(amount).strip())
            if amount_decimal <= Decimal("0.00"):
                raise InvalidPaymentAmountError("Payment amount must be a positive number greater than zero.")
        except (InvalidOperation, ValueError, TypeError):
            raise InvalidPaymentAmountError("Payment amount must be a valid numeric monetary value.")

        payroll_net = Decimal(str(payroll["net_pay"]))
        if amount_decimal != payroll_net:
            raise InvalidPaymentAmountError(
                f"Payment amount (₹{amount_decimal:,.2f}) does not match the approved payroll net salary (₹{payroll_net:,.2f})."
            )

        # 4. Validate payment method
        clean_method = payment_method.strip().upper()
        if clean_method not in PAYMENT_METHODS:
            raise PaymentProcessingError(
                f"Invalid payment method '{payment_method}'. Permitted methods: {', '.join(PAYMENT_METHODS)}."
            )

        # 5. Validate payment reference uniqueness
        clean_reference = payment_reference.strip()
        if not clean_reference:
            clean_reference = self.payment_repo.generate_payment_reference(clean_method, payroll["payroll_code"])
        else:
            duplicate = self.payment_repo.get_by_reference(clean_reference)
            if duplicate:
                raise DuplicatePaymentReferenceError(
                    f"Payment reference '{clean_reference}' has already been used in transaction #{duplicate['id']}. "
                    "Duplicate transaction references are strictly rejected for financial audit integrity."
                )

        # 6. Validate payment date
        if not payment_date:
            payment_date = date.today()

        # 7. Record transaction with academic simulation note
        academic_note = f"[Academic Record - No Real Bank Transfer Conducted]"
        full_notes = f"{transaction_notes.strip()}\n{academic_note}" if transaction_notes else academic_note

        new_payment_id = self.payment_repo.record_payment_transaction(
            payroll_id=payroll_id,
            payment_reference=clean_reference,
            payment_method=clean_method,
            amount_paid=amount_decimal,
            payment_date=payment_date,
            status=status.upper(),
            transaction_notes=full_notes,
        )

        logger.info(
            "Recorded payment voucher #%s (%s) for payroll #%s (%s, Status: %s)",
            new_payment_id, clean_reference, payroll_id, payroll["payroll_code"], status.upper()
        )
        return new_payment_id

    def transition_payment_status(
        self, payment_id: int, target_status: str, reason: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Transition payment voucher status with concurrency and financial integrity safeguards.
        
        Permitted transitions:
        - SUCCESSFUL -> REVERSED (Requires explicit reason; rolls back payroll from PAID to APPROVED)
        - PENDING -> SUCCESSFUL (Confirms payment; updates payroll from APPROVED to PAID)
        - PENDING -> FAILED / REVERSED (Fails/reverses pending payment; payroll remains APPROVED)
        """
        payment = self.payment_repo.get_by_id(payment_id)
        if not payment:
            return False, f"Payment record #{payment_id} was not found."

        current_status = payment["status"].upper()
        target_status = target_status.upper()

        if current_status == target_status:
            return True, f"Payment #{payment_id} is already in {target_status} status."

        # Reversal requires explicit reason
        if target_status == "REVERSED" and not reason:
            return False, "An explicit cancellation or reversal reason is mandatory for financial audit compliance."

        try:
            self.payment_repo.update_payment_status(
                payment_id=payment_id,
                target_status=target_status,
                reason=reason,
            )
            return True, f"Payment {payment['payment_reference']} status successfully transitioned to {target_status}."
        except Exception as err:
            logger.error("Error transitioning payment #%s to %s: %s", payment_id, target_status, err)
            return False, str(err)

    def get_salary_slip_data(self, payroll_id: int) -> Dict[str, Any]:
        """
        Gathers complete verified data for rendering or printing the official salary slip.
        """
        payroll = self.payroll_repo.get_by_id(payroll_id)
        if not payroll:
            raise PaymentProcessingError(f"Payroll statement #{payroll_id} does not exist.")

        emp_id = payroll["employee_id"]
        year = payroll["year"]
        month = payroll["month"]

        employee = self.employee_repo.get_by_id(emp_id)
        attendance = self.attendance_repo.get_by_employee_and_period(emp_id, year, month)
        salary_cfg = self.salary_repo.get_by_employee_id(emp_id)
        payment = self.payment_repo.get_by_payroll_id(payroll_id)

        month_name = MONTH_NAMES[month] if 1 <= month <= 12 else str(month)

        return {
            "payroll": payroll,
            "employee": employee,
            "attendance": attendance,
            "salary_cfg": salary_cfg,
            "payment": payment,
            "month_name": month_name,
            "year": year,
            "month": month,
            "is_paid": payroll["status"].upper() == "PAID",
        }

    def generate_salary_slip_pdf(self, payroll_id: int) -> bytes:
        """
        Generate an official, printable PDF salary slip using ReportLab.
        Returns the raw PDF bytes.
        """
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        slip_data = self.get_salary_slip_data(payroll_id)
        payroll = slip_data["payroll"]
        emp = slip_data["employee"]
        att = slip_data["attendance"]
        pm = slip_data["payment"]
        month_name = slip_data["month_name"]
        year = slip_data["year"]

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        normal_style = styles["Normal"]

        # Custom Paragraph Styles
        header_title = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1e293b"),
        )
        subtitle_style = ParagraphStyle(
            "SubTitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#64748b"),
        )
        academic_disclaimer = ParagraphStyle(
            "AcademicDisclaimer",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            alignment=1,  # Center
            textColor=colors.HexColor("#b45309"),
        )
        section_heading = ParagraphStyle(
            "SecHead",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#0f172a"),
        )
        table_cell = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
        )
        table_cell_bold = ParagraphStyle(
            "TableCellBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1e293b"),
        )
        amount_style = ParagraphStyle(
            "AmountCell",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            alignment=2,  # Right
            textColor=colors.HexColor("#0f172a"),
        )
        net_amount_style = ParagraphStyle(
            "NetPayAmount",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            alignment=2,  # Right
            textColor=colors.HexColor("#15803d"),
        )

        elements = []

        # 1. Academic Disclaimer Banner
        elements.append(
            Table(
                [[Paragraph("ACADEMIC RECORD ONLY &bull; NO REAL MONEY WAS TRANSFERRED", academic_disclaimer)]],
                colWidths=[523],
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef3c7")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#f59e0b")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]),
            )
        )
        elements.append(Spacer(1, 10))

        # 2. Company & Payslip Header
        header_table = Table(
            [
                [
                    Paragraph("<b>PayMaster Pro</b><br/><font size=8 color='#64748b'>Enterprise Payroll Management System</font>", header_title),
                    Paragraph(
                        f"<b>SALARY SLIP</b><br/>"
                        f"<font size=8 color='#64748b'>Period: <b>{month_name} {year}</b><br/>"
                        f"Statement Code: <b>{payroll['payroll_code']}</b><br/>"
                        f"Status: <b>{payroll['status']}</b></font>",
                        ParagraphStyle("RightHead", parent=normal_style, alignment=2, leading=11),
                    ),
                ]
            ],
            colWidths=[300, 223],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]),
        )
        elements.append(header_table)
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceBefore=6, spaceAfter=10))

        # 3. Employee Information & Attendance Table
        days_worked = f"{att['days_worked']} days" if att else "N/A"
        working_days = f"{att['total_working_days']} days" if att else "N/A"
        unpaid_leaves = f"{att['unpaid_leave_days']} days" if att else "0 days"
        ot_hours = f"{att['overtime_hours']} hrs" if att else "0 hrs"

        emp_info_data = [
            [
                Paragraph("<b>Employee Name:</b>", table_cell),
                Paragraph(f"{emp['first_name']} {emp['last_name']}", table_cell_bold),
                Paragraph("<b>Total Working Days:</b>", table_cell),
                Paragraph(working_days, table_cell),
            ],
            [
                Paragraph("<b>Employee Code:</b>", table_cell),
                Paragraph(f"{emp['employee_code']}", table_cell_bold),
                Paragraph("<b>Days Worked:</b>", table_cell),
                Paragraph(days_worked, table_cell_bold),
            ],
            [
                Paragraph("<b>Department:</b>", table_cell),
                Paragraph(f"{emp['department']}", table_cell),
                Paragraph("<b>Unpaid Leave Days:</b>", table_cell),
                Paragraph(unpaid_leaves, table_cell),
            ],
            [
                Paragraph("<b>Designation:</b>", table_cell),
                Paragraph(f"{emp['designation']}", table_cell),
                Paragraph("<b>Overtime Logged:</b>", table_cell),
                Paragraph(ot_hours, table_cell),
            ],
        ]

        emp_table = Table(emp_info_data, colWidths=[120, 150, 120, 133])
        emp_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        elements.append(emp_table)
        elements.append(Spacer(1, 14))

        # 4. Itemized Earnings & Deductions Table
        financial_table_data = [
            [
                Paragraph("<b>EARNINGS &amp; ALLOWANCES</b>", table_cell_bold),
                Paragraph("<b>AMOUNT (INR)</b>", ParagraphStyle("RightBold", parent=amount_style, alignment=2)),
                Paragraph("<b>DEDUCTIONS &amp; RECOVERIES</b>", table_cell_bold),
                Paragraph("<b>AMOUNT (INR)</b>", ParagraphStyle("RightBold", parent=amount_style, alignment=2)),
            ],
            [
                Paragraph("Basic Salary", table_cell),
                Paragraph(f"₹{float(payroll['basic_pay']):,.2f}", amount_style),
                Paragraph("Unpaid Leave Deduction", table_cell),
                Paragraph(f"-₹{float(payroll['leave_deduction']):,.2f}", amount_style),
            ],
            [
                Paragraph("Monthly Allowances Pool", table_cell),
                Paragraph(f"+₹{float(payroll['allowances_total']):,.2f}", amount_style),
                Paragraph("Other Standard Deductions", table_cell),
                Paragraph(f"-₹{float(payroll['other_deductions']):,.2f}", amount_style),
            ],
            [
                Paragraph("Overtime Compensation", table_cell),
                Paragraph(f"+₹{float(payroll['overtime_pay']):,.2f}", amount_style),
                Paragraph("Statutory Tax / PF", table_cell),
                Paragraph(f"-₹{float(payroll.get('tax_deduction', 0) + payroll.get('pf_deduction', 0)):,.2f}", amount_style),
            ],
            [
                Paragraph("<b>Total Gross Salary:</b>", table_cell_bold),
                Paragraph(f"<b>₹{float(payroll['gross_pay']):,.2f}</b>", amount_style),
                Paragraph("<b>Total Deductions:</b>", table_cell_bold),
                Paragraph(f"<b>-₹{float(payroll['total_deductions']):,.2f}</b>", amount_style),
            ],
        ]

        fin_table = Table(financial_table_data, colWidths=[160, 101, 160, 102])
        fin_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f8fafc")),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#94a3b8")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        elements.append(fin_table)
        elements.append(Spacer(1, 12))

        # 5. Net Salary Take-Home Banner
        net_table = Table(
            [
                [
                    Paragraph("<b>OFFICIAL NET SALARY DISBURSEMENT:</b><br/><font size=8 color='#64748b'>Total Gross Salary minus Total Deductions</font>", table_cell),
                    Paragraph(f"<b>₹{float(payroll['net_pay']):,.2f}</b>", net_amount_style),
                ]
            ],
            colWidths=[320, 203],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#dcfce7")),
                ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#22c55e")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]),
        )
        elements.append(net_table)
        elements.append(Spacer(1, 14))

        # 6. Payment Confirmation Box (if paid/recorded)
        if pm:
            pm_data = [
                [
                    Paragraph("<b>Payment Status:</b>", table_cell),
                    Paragraph(f"<b>{pm['status']}</b>", table_cell_bold),
                    Paragraph("<b>Payment Method:</b>", table_cell),
                    Paragraph(f"{pm['payment_method']}", table_cell),
                ],
                [
                    Paragraph("<b>Payment Date:</b>", table_cell),
                    Paragraph(f"{pm['payment_date']}", table_cell),
                    Paragraph("<b>Transaction Reference:</b>", table_cell),
                    Paragraph(f"{pm['payment_reference']}", table_cell_bold),
                ],
            ]
        else:
            pm_data = [
                [
                    Paragraph("<b>Payment Status:</b>", table_cell),
                    Paragraph(f"AWAITING DISBURSEMENT ({payroll['status']})", table_cell_bold),
                    Paragraph("<b>Disbursement Date:</b>", table_cell),
                    Paragraph("Pending Payment Recording", table_cell),
                ]
            ]

        pm_table = Table(pm_data, colWidths=[120, 150, 120, 133])
        pm_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        elements.append(pm_table)
        elements.append(Spacer(1, 24))

        # 7. Signatures / Audit Footer
        sig_table = Table(
            [
                [
                    Paragraph("____________________________<br/><b>Employee Signature</b>", table_cell),
                    Paragraph("____________________________<br/><b>Finance Manager Authorization</b>", ParagraphStyle("RightSig", parent=table_cell, alignment=2)),
                ]
            ],
            colWidths=[260, 263],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]),
        )
        elements.append(sig_table)
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<font size=7 color='#94a3b8'>Generated electronically on {date.today().isoformat()} &bull; PayMaster Pro Payroll Engine &bull; Academic Demonstration</font>", ParagraphStyle("Footer", parent=normal_style, alignment=1)))

        doc.build(elements)
        return buf.getvalue()
