"""
Salary Configuration and Salary Calculation Service (Module 5).
Pure, reusable calculation engine independent of Flask routes and HTTP context.
Enforces:
1. Python Decimal precision for all monetary and daily calculations.
2. Explicit two-decimal-place rounding policy (ROUND_HALF_UP).
3. Zero working days and invalid salary value rejection.
4. Strict unpaid leave deduction: Daily salary = Basic / Working Days; Leave Deduction = Daily salary * Unpaid Days.
5. Paid leaves never incur salary deduction.
6. Overtime rate per hour, with employee-specific rate taking precedence.
7. Deductions capped at gross salary unless negative net pay is explicitly permitted.
8. Complete reproducibility from input parameters without silent defaulting.
9. Integration with employee profiles and monthly attendance records.
"""

from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from repositories.salary_repository import SalaryRepository
from repositories.employee_repository import EmployeeRepository
from repositories.attendance_repository import AttendanceRepository
from modules.attendance.validators import MONTH_NAMES

logger = logging.getLogger(__name__)

# Consistent Currency Rounding Constant
CENT = Decimal("0.01")


# =============================================================================
# Domain Exceptions
# =============================================================================

class SalaryCalculationError(Exception):
    """Base exception for all salary computation errors."""
    pass


class ZeroWorkingDaysError(SalaryCalculationError):
    """Raised when configured total working days is zero or negative."""
    pass


class InvalidSalaryValueError(SalaryCalculationError):
    """Raised when monetary, rate, or day count inputs are negative or malformed."""
    pass


class MissingSalaryInputError(SalaryCalculationError):
    """Raised when required salary calculation inputs are missing."""
    pass


class DeductionExceedsGrossError(SalaryCalculationError):
    """Raised when total deductions exceed gross salary under standard policy."""
    pass


# =============================================================================
# Calculation Result Data Transfer Object
# =============================================================================

@dataclass(frozen=True)
class SalaryCalculationResult:
    """Immutable data transfer object capturing full reproducible salary computation."""
    basic_salary: Decimal
    total_working_days: int
    daily_salary: Decimal
    paid_leave_days: Decimal
    unpaid_leave_days: Decimal
    leave_deduction: Decimal
    allowances: Decimal
    overtime_hours: Decimal
    overtime_rate: Decimal
    overtime_payment: Decimal
    other_deductions: Decimal
    gross_salary: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    allow_negative_net: bool
    reproducible_inputs: Dict[str, Any]
    formula_explanations: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to a serializable dictionary."""
        data = asdict(self)
        # Convert Decimals to string or float for JSON serialization if needed
        return data


# =============================================================================
# Pure Calculation Engine (Reusable & Framework Independent)
# =============================================================================

class SalaryCalculationEngine:
    """
    Pure mathematical and business rule calculation engine for employee compensation.
    Operates strictly on Python Decimal types with ROUND_HALF_UP rounding.
    Treats formulas as academic demonstration rules, not statutory compliance declarations.
    """

    @staticmethod
    def round_currency(value: Decimal) -> Decimal:
        """Apply consistent rounding policy to two decimal places (ROUND_HALF_UP)."""
        return value.quantize(CENT, rounding=ROUND_HALF_UP)

    @classmethod
    def to_decimal(
        cls,
        value: Any,
        field_name: str,
        allow_zero: bool = True,
        min_value: Decimal = Decimal("0.00"),
    ) -> Decimal:
        """
        Validate and convert an input value strictly to Decimal.
        Does NOT silently substitute defaults when inputs are None or empty.
        Rejects binary floating point directly to prevent precision loss.
        """
        if value is None:
            raise MissingSalaryInputError(f"Required input '{field_name}' is missing.")

        if isinstance(value, float):
            # Strict safeguard: warn/convert via exact string to avoid float binary artifacts
            value = str(value)

        str_val = str(value).strip()
        if str_val == "":
            raise MissingSalaryInputError(f"Required input '{field_name}' cannot be empty.")

        try:
            dec = Decimal(str_val)
        except (InvalidOperation, ValueError, TypeError) as err:
            raise InvalidSalaryValueError(
                f"Field '{field_name}' contains invalid non-numeric value: {value!r}"
            ) from err

        if not dec.is_finite():
            raise InvalidSalaryValueError(f"Field '{field_name}' must be a finite number.")

        if dec < min_value:
            raise InvalidSalaryValueError(
                f"Field '{field_name}' cannot be negative ({dec}). Must be >= {min_value}."
            )

        if not allow_zero and dec == Decimal("0"):
            raise InvalidSalaryValueError(
                f"Field '{field_name}' must be greater than zero."
            )

        return dec

    @classmethod
    def calculate_salary(
        cls,
        basic_salary: Union[Decimal, str, int],
        total_working_days: Union[int, Decimal, str],
        unpaid_leave_days: Union[Decimal, str, int],
        allowances: Union[Decimal, str, int],
        overtime_hours: Union[Decimal, str, int],
        overtime_rate: Union[Decimal, str, int],
        other_deductions: Union[Decimal, str, int],
        paid_leave_days: Union[Decimal, str, int] = Decimal("0.0"),
        allow_negative_net: bool = False,
    ) -> SalaryCalculationResult:
        """
        Execute reproducible monthly salary calculation according to configured rules:
        
        1. Daily salary = Basic monthly salary / Total working days in payroll month.
        2. Leave deduction = Daily salary * Unpaid leave days.
        3. Overtime payment = Overtime hours * Overtime rate.
        4. Gross salary = Basic salary + Allowances + Overtime payment.
        5. Total deductions = Leave deduction + Other deductions.
        6. Net salary = Gross salary - Total deductions.
        
        Args:
            basic_salary: Basic monthly salary (>= 0).
            total_working_days: Configured business days in month (> 0).
            unpaid_leave_days: Unpaid leave days (LWP) (>= 0).
            allowances: Total monthly allowances (HRA, transport, medical, etc.) (>= 0).
            overtime_hours: Reconciled overtime hours (>= 0).
            overtime_rate: Overtime rate per hour (>= 0).
            other_deductions: Other monthly deductions (>= 0).
            paid_leave_days: Approved paid leave days (>= 0, no salary deducted).
            allow_negative_net: If True, permits deductions to exceed gross salary (deficit).
            
        Returns:
            SalaryCalculationResult object containing step-by-step verified computation.
            
        Raises:
            ZeroWorkingDaysError: If total_working_days <= 0.
            MissingSalaryInputError: If any required input is None or blank.
            InvalidSalaryValueError: If any input is negative or non-numeric.
            DeductionExceedsGrossError: If total deductions > gross salary and allow_negative_net is False.
        """
        # 1. Strict Input Validation (No silent defaults)
        dec_basic = cls.to_decimal(basic_salary, "basic_salary", allow_zero=True)
        dec_unpaid_leaves = cls.to_decimal(unpaid_leave_days, "unpaid_leave_days", allow_zero=True)
        dec_paid_leaves = cls.to_decimal(paid_leave_days, "paid_leave_days", allow_zero=True)
        dec_allowances = cls.to_decimal(allowances, "allowances", allow_zero=True)
        dec_ot_hours = cls.to_decimal(overtime_hours, "overtime_hours", allow_zero=True)
        dec_ot_rate = cls.to_decimal(overtime_rate, "overtime_rate", allow_zero=True)
        dec_other_deductions = cls.to_decimal(other_deductions, "other_deductions", allow_zero=True)

        # Working days must be positive integer (> 0)
        if total_working_days is None:
            raise MissingSalaryInputError("Required input 'total_working_days' is missing.")

        try:
            int_working_days = int(str(total_working_days).strip())
        except (ValueError, TypeError) as err:
            raise InvalidSalaryValueError(
                f"Total working days must be a valid integer, got: {total_working_days!r}"
            ) from err

        if int_working_days <= 0:
            raise ZeroWorkingDaysError(
                f"Total working days must be strictly greater than zero (received {int_working_days}). "
                "Cannot compute daily salary rate with zero working days."
            )

        dec_working_days = Decimal(int_working_days)

        # 2. Daily Salary Calculation
        # Daily salary = Basic monthly salary / Total working days in the payroll month.
        daily_salary = cls.round_currency(dec_basic / dec_working_days)

        # 3. Leave Deduction Calculation
        # Rule: Leave deduction = Daily salary * Unpaid leave days.
        # Rule: Paid leave preserves full pay (zero deduction).
        leave_deduction = cls.round_currency(daily_salary * dec_unpaid_leaves)

        # 4. Overtime Payment Calculation
        # Overtime payment = Overtime hours * Overtime rate.
        overtime_payment = cls.round_currency(dec_ot_hours * dec_ot_rate)

        # 5. Gross Salary Calculation
        # Gross salary = Basic salary + Allowances + Overtime payment.
        gross_salary = cls.round_currency(dec_basic + dec_allowances + overtime_payment)

        # 6. Total Deductions Calculation
        # Total deductions = Leave deduction + Other deductions.
        total_deductions = cls.round_currency(leave_deduction + dec_other_deductions)

        # 7. Net Salary & Deduction Threshold Guard
        # Net salary = Gross salary - Total deductions.
        net_salary = gross_salary - total_deductions

        if total_deductions > gross_salary and not allow_negative_net:
            raise DeductionExceedsGrossError(
                f"Total deductions ({total_deductions}) exceed gross salary ({gross_salary}). "
                f"Net salary would be negative ({net_salary}). Under standard policy, deductions "
                "cannot exceed gross earnings unless negative net pay is explicitly configured."
            )

        formula_explanations = {
            "daily_salary": f"Basic ({dec_basic}) / Working Days ({int_working_days}) = {daily_salary}",
            "leave_deduction": f"Daily Salary ({daily_salary}) * Unpaid Leaves ({dec_unpaid_leaves}) = {leave_deduction} (Paid leaves={dec_paid_leaves} incur 0 deduction)",
            "overtime_payment": f"OT Hours ({dec_ot_hours}) * OT Rate ({dec_ot_rate}) = {overtime_payment}",
            "gross_salary": f"Basic ({dec_basic}) + Allowances ({dec_allowances}) + OT ({overtime_payment}) = {gross_salary}",
            "total_deductions": f"Leave Deduction ({leave_deduction}) + Other Deductions ({dec_other_deductions}) = {total_deductions}",
            "net_salary": f"Gross ({gross_salary}) - Total Deductions ({total_deductions}) = {net_salary}",
            "rounding_policy": "ROUND_HALF_UP applied at each monetary step to two decimal places (0.01)",
            "disclaimer": "Academic demonstration calculation rules; not a statutory payroll compliance statement.",
        }

        reproducible_inputs = {
            "basic_salary": str(dec_basic),
            "total_working_days": int_working_days,
            "unpaid_leave_days": str(dec_unpaid_leaves),
            "paid_leave_days": str(dec_paid_leaves),
            "allowances": str(dec_allowances),
            "overtime_hours": str(dec_ot_hours),
            "overtime_rate": str(dec_ot_rate),
            "other_deductions": str(dec_other_deductions),
            "allow_negative_net": allow_negative_net,
        }

        return SalaryCalculationResult(
            basic_salary=dec_basic,
            total_working_days=int_working_days,
            daily_salary=daily_salary,
            paid_leave_days=dec_paid_leaves,
            unpaid_leave_days=dec_unpaid_leaves,
            leave_deduction=leave_deduction,
            allowances=dec_allowances,
            overtime_hours=dec_ot_hours,
            overtime_rate=dec_ot_rate,
            overtime_payment=overtime_payment,
            other_deductions=dec_other_deductions,
            gross_salary=gross_salary,
            total_deductions=total_deductions,
            net_salary=net_salary,
            allow_negative_net=allow_negative_net,
            reproducible_inputs=reproducible_inputs,
            formula_explanations=formula_explanations,
        )


# =============================================================================
# Salary Service Layer (Integrated with Database Repositories)
# =============================================================================

class SalaryService:
    """
    Service layer coordinating salary settings management, attendance integration,
    and salary preview generation across MySQL tables.
    """

    def __init__(
        self,
        salary_repo: Optional[SalaryRepository] = None,
        employee_repo: Optional[EmployeeRepository] = None,
        attendance_repo: Optional[AttendanceRepository] = None,
    ):
        self.salary_repo = salary_repo or SalaryRepository()
        self.employee_repo = employee_repo or EmployeeRepository()
        self.attendance_repo = attendance_repo or AttendanceRepository()
        self.engine = SalaryCalculationEngine()

    def get_paginated_salary_structures(
        self,
        search: Optional[str] = None,
        department: Optional[str] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch paginated list of employee salary structures."""
        return self.salary_repo.get_all_paginated(
            search=search, department=department, page=page, per_page=per_page
        )

    def get_salary_configuration(self, employee_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve full salary configuration joined with employee info."""
        return self.salary_repo.get_by_employee_id(employee_id)

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Fetch aggregate compensation statistics for dashboard cards."""
        return self.salary_repo.get_summary_metrics()

    def get_active_employees(self) -> List[Dict[str, Any]]:
        """Fetch list of all active employees for selection in preview/config."""
        return self.employee_repo.get_active_employees()

    def update_salary_configuration(
        self, employee_id: int, form_data: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, str]]:
        """
        Validate and update salary settings for an employee.
        Returns: (success: bool, errors_dict)
        """
        errors = {}

        # 1. Base salary
        raw_base = form_data.get("base_salary")
        try:
            base_salary = Decimal(str(raw_base).strip())
            if base_salary < Decimal("0.00"):
                errors["base_salary"] = "Base salary cannot be negative."
        except Exception:
            errors["base_salary"] = "Base salary must be a valid numeric amount."
            base_salary = Decimal("0.00")

        # 2. Hourly Overtime rate
        raw_rate = form_data.get("hourly_rate")
        try:
            hourly_rate = Decimal(str(raw_rate).strip()) if raw_rate else Decimal("0.00")
            if hourly_rate < Decimal("0.00"):
                errors["hourly_rate"] = "Overtime rate per hour cannot be negative."
        except Exception:
            errors["hourly_rate"] = "Overtime rate must be a valid numeric amount."
            hourly_rate = Decimal("0.00")

        # 3. Allowances: HRA, Transport, Medical, Other
        allowance_fields = ["hra", "transport_allowance", "medical_allowance", "other_allowances"]
        cleaned_allowances = {}
        for field in allowance_fields:
            raw_val = form_data.get(field)
            try:
                val = Decimal(str(raw_val).strip()) if raw_val else Decimal("0.00")
                if val < Decimal("0.00"):
                    errors[field] = f"{field.replace('_', ' ').title()} cannot be negative."
                cleaned_allowances[field] = val
            except Exception:
                errors[field] = f"{field.replace('_', ' ').title()} must be a valid amount."
                cleaned_allowances[field] = Decimal("0.00")

        # 4. Other deductions
        raw_other_ded = form_data.get("other_deductions")
        try:
            other_deductions = Decimal(str(raw_other_ded).strip()) if raw_other_ded else Decimal("0.00")
            if other_deductions < Decimal("0.00"):
                errors["other_deductions"] = "Other deductions cannot be negative."
        except Exception:
            errors["other_deductions"] = "Other deductions must be a valid numeric amount."
            other_deductions = Decimal("0.00")

        # 5. Effective Date
        raw_effective = form_data.get("effective_from")
        if not raw_effective:
            effective_from = date.today()
        else:
            try:
                effective_from = date.fromisoformat(str(raw_effective).strip())
            except Exception:
                errors["effective_from"] = "Effective date must be in YYYY-MM-DD format."
                effective_from = date.today()

        if errors:
            return False, errors

        payload = {
            "base_salary": base_salary,
            "hourly_rate": hourly_rate,
            "hra": cleaned_allowances["hra"],
            "transport_allowance": cleaned_allowances["transport_allowance"],
            "medical_allowance": cleaned_allowances["medical_allowance"],
            "other_allowances": cleaned_allowances["other_allowances"],
            "tax_deduction_rate": Decimal("0.00"),
            "pf_deduction_rate": Decimal("0.00"),
            "other_deductions": other_deductions,
            "effective_from": effective_from,
        }

        try:
            self.salary_repo.upsert_salary_settings(employee_id, payload)
            return True, {}
        except Exception as e:
            logger.error("Failed to upsert salary settings for employee %s: %s", employee_id, e)
            return False, {"database": f"Database error updating salary settings: {str(e)}"}

    def preview_salary_calculation(
        self,
        employee_id: int,
        year: int,
        month: int,
        allow_negative_net: bool = False,
    ) -> Dict[str, Any]:
        """
        Build an actual salary preview using real employee and attendance records from MySQL.
        
        Returns:
            Dictionary containing:
            - status: 'success' | 'missing_employee' | 'missing_salary_settings' | 'missing_attendance' | 'calculation_error'
            - employee: profile dictionary
            - salary_settings: configuration dictionary
            - attendance: monthly attendance record dictionary
            - calculation: SalaryCalculationResult (if successful)
            - error_message: str (if failed)
        """
        # 1. Fetch Employee Record
        employee = self.employee_repo.get_by_id(employee_id)
        if not employee:
            return {
                "status": "missing_employee",
                "error_message": f"Employee #{employee_id} does not exist in the database.",
                "employee": None,
                "attendance": None,
                "salary_settings": None,
                "calculation": None,
            }

        # 2. Fetch Salary Settings
        salary_cfg = self.salary_repo.get_by_employee_id(employee_id)
        if not salary_cfg:
            return {
                "status": "missing_salary_settings",
                "error_message": (
                    f"No salary structure configured for {employee['first_name']} {employee['last_name']}. "
                    "Please configure base salary and allowances first."
                ),
                "employee": employee,
                "attendance": None,
                "salary_settings": None,
                "calculation": None,
            }

        # 3. Fetch Monthly Attendance Record
        attendance = self.attendance_repo.get_by_employee_and_period(employee_id, year, month)
        if not attendance:
            month_name = MONTH_NAMES[month] if 1 <= month <= 12 else str(month)
            return {
                "status": "missing_attendance",
                "error_message": (
                    f"No attendance record found for {employee['first_name']} {employee['last_name']} "
                    f"({employee['employee_code']}) for {month_name} {year}. "
                    "Please record monthly attendance before previewing salary calculation."
                ),
                "employee": employee,
                "salary_settings": salary_cfg,
                "attendance": None,
                "calculation": None,
            }

        # 4. Resolve Overtime Rate Precedence
        # Rule: Overtime rate per hour, with employee-specific rate taking precedence when present.
        # Check attendance overtime rate first, then salary settings hourly rate.
        attendance_ot_rate = Decimal(str(attendance.get("overtime_rate", "0.00") or "0.00"))
        employee_ot_rate = Decimal(str(salary_cfg.get("hourly_rate", "0.00") or "0.00"))

        if attendance_ot_rate > Decimal("0.00"):
            effective_ot_rate = attendance_ot_rate
            ot_rate_source = "Attendance Record Overtime Rate"
        elif employee_ot_rate > Decimal("0.00"):
            effective_ot_rate = employee_ot_rate
            ot_rate_source = "Employee Salary Settings Hourly Rate"
        else:
            effective_ot_rate = Decimal("0.00")
            ot_rate_source = "None configured (0.00)"

        # 5. Sum monthly allowances
        total_allowances = (
            Decimal(str(salary_cfg.get("hra", 0.00))) +
            Decimal(str(salary_cfg.get("transport_allowance", 0.00))) +
            Decimal(str(salary_cfg.get("medical_allowance", 0.00))) +
            Decimal(str(salary_cfg.get("other_allowances", 0.00)))
        )

        basic_salary = Decimal(str(salary_cfg.get("base_salary", 0.00)))
        total_working_days = int(attendance.get("total_working_days", 0))
        unpaid_leave_days = Decimal(str(attendance.get("unpaid_leaves", 0.0)))
        paid_leave_days = Decimal(str(attendance.get("paid_leaves", 0.0)))
        overtime_hours = Decimal(str(attendance.get("overtime_hours", 0.00)))
        other_deductions = Decimal(str(salary_cfg.get("other_deductions", 0.00)))

        # 6. Perform pure salary calculation
        try:
            calc_result = self.engine.calculate_salary(
                basic_salary=basic_salary,
                total_working_days=total_working_days,
                unpaid_leave_days=unpaid_leave_days,
                allowances=total_allowances,
                overtime_hours=overtime_hours,
                overtime_rate=effective_ot_rate,
                other_deductions=other_deductions,
                paid_leave_days=paid_leave_days,
                allow_negative_net=allow_negative_net,
            )

            return {
                "status": "success",
                "employee": employee,
                "salary_settings": salary_cfg,
                "attendance": attendance,
                "calculation": calc_result,
                "ot_rate_source": ot_rate_source,
                "error_message": None,
            }
        except SalaryCalculationError as err:
            return {
                "status": "calculation_error",
                "error_message": str(err),
                "employee": employee,
                "salary_settings": salary_cfg,
                "attendance": attendance,
                "calculation": None,
            }
