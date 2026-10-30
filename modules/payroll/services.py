"""
Monthly Payroll Processing service layer (Module 6).
Coordinates monthly payroll runs, single employee generation, eligibility audits,
salary snapshot preservation, and status transitions with concurrency safeguards.
Strictly delegates mathematical computations to SalaryCalculationEngine.
"""

from datetime import date
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple

from repositories.payroll_repository import PayrollRepository
from repositories.employee_repository import EmployeeRepository
from repositories.attendance_repository import AttendanceRepository
from repositories.salary_repository import SalaryRepository
from modules.salary.services import SalaryCalculationEngine, SalaryCalculationError, SalaryService
from modules.attendance.validators import MONTH_NAMES

logger = logging.getLogger(__name__)


class PayrollProcessingError(Exception):
    """Base exception for payroll generation and workflow errors."""
    pass


class DuplicatePayrollError(PayrollProcessingError):
    """Raised when an attempt is made to generate a duplicate payroll record."""
    pass


class MissingPayrollInputsError(PayrollProcessingError):
    """Raised when attendance or salary settings are missing for an employee."""
    pass


class InvalidStatusTransitionError(PayrollProcessingError):
    """Raised when an invalid or forbidden status change is attempted."""
    pass


class PayrollService:
    """
    Service coordinating monthly payroll runs, eligibility audits,
    snapshot persistence, and status lifecycle transitions.
    """

    def __init__(
        self,
        payroll_repo: Optional[PayrollRepository] = None,
        employee_repo: Optional[EmployeeRepository] = None,
        attendance_repo: Optional[AttendanceRepository] = None,
        salary_repo: Optional[SalaryRepository] = None,
    ):
        self.payroll_repo = payroll_repo or PayrollRepository()
        self.employee_repo = employee_repo or EmployeeRepository()
        self.attendance_repo = attendance_repo or AttendanceRepository()
        self.salary_repo = salary_repo or SalaryRepository()
        self.salary_service = SalaryService(
            salary_repo=self.salary_repo,
            employee_repo=self.employee_repo,
            attendance_repo=self.attendance_repo,
        )

    def get_eligible_employees_for_period(
        self, year: int, month: int
    ) -> List[Dict[str, Any]]:
        """
        Audit all active employees for the selected payroll period.
        Annotates each with:
        - has_attendance: bool
        - has_salary_settings: bool
        - existing_payroll: Optional[Dict]
        - is_eligible: bool (ready for payroll generation)
        """
        active_employees = self.employee_repo.get_active_employees()
        audited_employees = []

        for emp in active_employees:
            emp_id = emp["id"]

            # 1. Check Attendance
            attendance = self.attendance_repo.get_by_employee_and_period(emp_id, year, month)
            has_attendance = attendance is not None

            # 2. Check Salary Settings
            salary_cfg = self.salary_repo.get_by_employee_id(emp_id)
            has_salary = salary_cfg is not None and salary_cfg.get("base_salary") is not None

            # 3. Check Existing Payroll
            existing_payroll = self.payroll_repo.get_by_employee_and_period(emp_id, year, month)

            # Eligible if: attendance exists, salary exists, and no active/draft payroll exists
            is_eligible = (
                has_attendance and
                has_salary and
                (existing_payroll is None or existing_payroll.get("status") == "CANCELLED")
            )

            audited_employees.append({
                "employee": emp,
                "has_attendance": has_attendance,
                "attendance": attendance,
                "has_salary_settings": has_salary,
                "salary_settings": salary_cfg,
                "existing_payroll": existing_payroll,
                "is_eligible": is_eligible,
            })

        return audited_employees

    def preview_employee_payroll(
        self, employee_id: int, year: int, month: int
    ) -> Dict[str, Any]:
        """
        Preview calculated salary components before saving to the database.
        Delegates entirely to SalaryService to ensure 100% calculation consistency.
        """
        return self.salary_service.preview_salary_calculation(
            employee_id=employee_id, year=year, month=month, allow_negative_net=False
        )

    def generate_single_payroll(
        self, employee_id: int, year: int, month: int, remarks: Optional[str] = None
    ) -> int:
        """
        Generate and persist a single employee monthly payroll record.
        Wraps operations in a database transaction with duplicate checks.
        
        Returns:
            Newly created payroll record ID.
            
        Raises:
            DuplicatePayrollError: If record for this period already exists.
            MissingPayrollInputsError: If attendance or salary settings are missing.
            PayrollProcessingError: If validation or calculation fails.
        """
        # 1. Duplicate check
        existing = self.payroll_repo.get_by_employee_and_period(employee_id, year, month)
        if existing and existing.get("status") in ("DRAFT", "GENERATED", "APPROVED", "PAID"):
            m_name = MONTH_NAMES[month] if 1 <= month <= 12 else str(month)
            raise DuplicatePayrollError(
                f"A payroll record for this employee for {m_name} {year} already exists "
                f"({existing['payroll_code']}, Status: {existing['status']}). "
                "Duplicate monthly payroll records are strictly prevented."
            )

        # 2. Preview & validate calculation using SalaryService
        preview_data = self.preview_employee_payroll(employee_id, year, month)
        status = preview_data.get("status")

        if status == "missing_employee":
            raise MissingPayrollInputsError(f"Employee #{employee_id} does not exist.")
        elif status == "missing_attendance":
            raise MissingPayrollInputsError(preview_data.get("error_message"))
        elif status == "missing_salary_settings":
            raise MissingPayrollInputsError(preview_data.get("error_message"))
        elif status == "calculation_error":
            raise PayrollProcessingError(preview_data.get("error_message"))
        elif status != "success":
            raise PayrollProcessingError("Unexpected error validating salary calculation.")

        calc = preview_data["calculation"]
        emp = preview_data["employee"]
        scfg = preview_data["salary_settings"]

        # 3. Build snapshot record
        payroll_code = self.payroll_repo.generate_payroll_code(year, month, emp["employee_code"])

        payload = {
            "payroll_code": payroll_code,
            "employee_id": employee_id,
            "year": year,
            "month": month,
            "basic_pay": calc.basic_salary,
            "allowances_total": calc.allowances,
            "overtime_pay": calc.overtime_payment,
            "gross_pay": calc.gross_salary,
            "leave_deduction": calc.leave_deduction,
            "tax_deduction": Decimal("0.00"),
            "pf_deduction": Decimal("0.00"),
            "other_deductions": calc.other_deductions,
            "total_deductions": calc.total_deductions,
            "net_pay": calc.net_salary,
            "status": "DRAFT",
            "generated_date": date.today(),
            "payment_due_date": None,
            "remarks": remarks or f"Monthly payroll for {MONTH_NAMES[month]} {year}",
        }

        # 4. Insert into database
        new_id = self.payroll_repo.create_payroll_record(payload)
        logger.info(
            "Generated payroll record #%s (%s) for employee #%s (%s-%02d)",
            new_id, payroll_code, employee_id, year, month
        )
        return new_id

    def generate_batch_payroll_run(
        self, year: int, month: int, employee_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Execute a controlled batch monthly payroll generation run for eligible employees.
        Processes each eligible employee within a transactional framework.
        
        Returns:
            Dictionary with execution summary:
            - successful: list of generated records
            - skipped: list of employees with explanation
            - total_processed: int
        """
        audited = self.get_eligible_employees_for_period(year, month)
        successful = []
        skipped = []

        # If a specific list of employee IDs was selected, filter to those
        if employee_ids is not None:
            id_set = set(employee_ids)
            audited = [a for a in audited if a["employee"]["id"] in id_set]

        for item in audited:
            emp = item["employee"]
            emp_id = emp["id"]

            if not item["is_eligible"]:
                reasons = []
                if not item["has_attendance"]:
                    reasons.append("Missing attendance record")
                if not item["has_salary_settings"]:
                    reasons.append("Missing salary structure")
                if item["existing_payroll"]:
                    reasons.append(f"Payroll already exists ({item['existing_payroll']['status']})")

                skipped.append({
                    "employee_id": emp_id,
                    "employee_code": emp["employee_code"],
                    "name": f"{emp['first_name']} {emp['last_name']}",
                    "reason": "; ".join(reasons) or "Ineligible",
                })
                continue

            try:
                new_id = self.generate_single_payroll(
                    employee_id=emp_id,
                    year=year,
                    month=month,
                    remarks=f"Batch monthly run for {MONTH_NAMES[month]} {year}"
                )
                successful.append({
                    "payroll_id": new_id,
                    "employee_id": emp_id,
                    "employee_code": emp["employee_code"],
                    "name": f"{emp['first_name']} {emp['last_name']}",
                })
            except Exception as e:
                logger.error("Failed to generate payroll in batch for employee #%s: %s", emp_id, e)
                skipped.append({
                    "employee_id": emp_id,
                    "employee_code": emp["employee_code"],
                    "name": f"{emp['first_name']} {emp['last_name']}",
                    "reason": f"Calculation error: {str(e)}",
                })

        return {
            "year": year,
            "month": month,
            "total_candidates": len(audited),
            "successful_count": len(successful),
            "skipped_count": len(skipped),
            "successful": successful,
            "skipped": skipped,
        }

    def transition_payroll_status(
        self,
        payroll_id: int,
        target_status: str,
        reason: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Transition payroll status through valid business workflows with concurrency safeguards.
        
        Valid transitions:
        - DRAFT -> APPROVED: Finalize and approve payroll statement.
        - DRAFT -> CANCELLED: Void draft record.
        - APPROVED -> DRAFT: Reopen for correction (explicit adjustment workflow).
        
        Protected rules:
        - PAID records can NEVER be transitioned in this module.
        - APPROVED records cannot be marked CANCELLED without reopening.
        - Do not mark payroll as PAID in this module (reserved for Module 7 payments).
        
        Returns:
            (success: bool, message: str)
        """
        record = self.payroll_repo.get_by_id(payroll_id)
        if not record:
            return False, f"Payroll record #{payroll_id} was not found."

        current_status = record["status"].upper()
        target_status = target_status.upper()

        if current_status == target_status:
            return True, f"Payroll record #{payroll_id} is already in {target_status} status."

        # Rule: Protected PAID state
        if current_status == "PAID":
            return False, (
                f"Payroll record {record['payroll_code']} is already marked as PAID. "
                "Paid statements represent confirmed financial disbursements and cannot be altered or cancelled."
            )

        # Rule: Module 6 cannot mark as PAID directly
        if target_status == "PAID":
            return False, (
                "Cannot mark payroll as PAID directly in the Payroll module. "
                "Disbursements must be executed and confirmed through the Payment Processing module (Module 7)."
            )

        # Transition 1: DRAFT -> APPROVED
        if current_status in ("DRAFT", "GENERATED") and target_status == "APPROVED":
            remarks = f"Approved on {date.today().isoformat()}" + (f": {reason}" if reason else "")
            ok = self.payroll_repo.update_payroll_status(
                payroll_id=payroll_id,
                new_status="APPROVED",
                expected_current_status=current_status,
                remarks=remarks,
            )
            if ok:
                return True, f"Payroll statement {record['payroll_code']} successfully approved."
            return False, "Failed to approve payroll due to concurrent modification. Please refresh and try again."

        # Transition 2: DRAFT -> CANCELLED
        if current_status in ("DRAFT", "GENERATED") and target_status == "CANCELLED":
            remarks = f"Cancelled on {date.today().isoformat()}" + (f": {reason}" if reason else "")
            ok = self.payroll_repo.update_payroll_status(
                payroll_id=payroll_id,
                new_status="CANCELLED",
                expected_current_status=current_status,
                remarks=remarks,
            )
            if ok:
                return True, f"Draft payroll {record['payroll_code']} has been cancelled."
            return False, "Failed to cancel payroll due to concurrent status change."

        # Transition 3: APPROVED -> DRAFT (Adjustment / Reopening workflow)
        if current_status == "APPROVED" and target_status == "DRAFT":
            if not reason:
                return False, "An explicit correction or adjustment reason is required to reopen an approved payroll record."
            remarks = f"Reopened for adjustment on {date.today().isoformat()}: {reason}"
            ok = self.payroll_repo.update_payroll_status(
                payroll_id=payroll_id,
                new_status="DRAFT",
                expected_current_status="APPROVED",
                remarks=remarks,
            )
            if ok:
                return True, f"Approved payroll {record['payroll_code']} reopened as DRAFT for adjustment."
            return False, "Failed to reopen approved payroll record. It may have been updated concurrently."

        # Any other transition is invalid
        raise InvalidStatusTransitionError(
            f"Invalid payroll status transition from '{current_status}' to '{target_status}'. "
            "Finalized records cannot be modified without an explicit adjustment workflow."
        )

    def get_payroll_details(self, payroll_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve complete payroll statement details, including attendance
        and salary configuration snapshots.
        """
        payroll = self.payroll_repo.get_by_id(payroll_id)
        if not payroll:
            return None

        emp_id = payroll["employee_id"]
        year = payroll["year"]
        month = payroll["month"]

        # Fetch attendance record for reference
        attendance = self.attendance_repo.get_by_employee_and_period(emp_id, year, month)
        # Fetch current salary settings for comparison/audit
        salary_cfg = self.salary_repo.get_by_employee_id(emp_id)

        return {
            "payroll": payroll,
            "attendance": attendance,
            "salary_settings": salary_cfg,
        }
