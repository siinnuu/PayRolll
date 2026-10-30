"""
Payment Repository for MySQL operations on the `payments` table.
Handles parameterized queries, transactions, status transitions,
concurrency safeguards, pagination, and financial disbursement summaries.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple
from repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class PaymentRepository(BaseRepository):
    """Repository handling CRUD, status transitions, and queries for salary disbursements."""

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    def generate_payment_reference(self, method: str, payroll_code: str) -> str:
        """
        Generate a unique, standardized payment transaction reference.
        Format: TXN-{YYYYMM}-{EMP_CODE}-{HEX}
        """
        import uuid
        parts = payroll_code.split("-")
        # e.g., payroll_code: PAY-2026-10-EMP001
        if len(parts) >= 4:
            year, month, emp_code = parts[1], parts[2], parts[3]
            short_id = uuid.uuid4().hex[:5].upper()
            return f"TXN-{year}{month}-{emp_code}-{short_id}"
        short_id = uuid.uuid4().hex[:8].upper()
        return f"TXN-{short_id}"

    def get_by_id(self, payment_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single payment disbursement voucher joined with payroll and employee."""
        try:
            query = """
                SELECT 
                    pm.id,
                    pm.id AS payment_id,
                    pm.payroll_id,
                    pm.payment_reference,
                    pm.payment_method,
                    pm.amount_paid,
                    pm.payment_date,
                    pm.status,
                    pm.transaction_notes,
                    pm.created_at,
                    pm.updated_at,
                    p.payroll_code,
                    p.year,
                    p.month,
                    p.basic_pay,
                    p.allowances_total,
                    p.overtime_pay,
                    p.gross_pay,
                    COALESCE(p.leave_deduction, 0.00) AS leave_deduction,
                    COALESCE(p.other_deductions, 0.00) AS other_deductions,
                    p.total_deductions,
                    p.net_pay,
                    p.status AS payroll_status,
                    e.id AS employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    CONCAT(e.first_name, ' ', e.last_name) AS full_name,
                    e.department,
                    e.designation,
                    e.email
                FROM payments pm
                JOIN payroll p ON pm.payroll_id = p.id
                JOIN employees e ON p.employee_id = e.id
                WHERE pm.id = %s
                LIMIT 1;
            """
            return self.execute_query(query, (payment_id,), fetch_one=True)
        except Exception as e:
            logger.error("Error fetching payment ID %s: %s", payment_id, e)
            return None

    def get_by_payroll_id(self, payroll_id: int) -> Optional[Dict[str, Any]]:
        """Fetch latest payment record associated with a given payroll record."""
        try:
            query = """
                SELECT 
                    pm.id,
                    pm.id AS payment_id,
                    pm.payroll_id,
                    pm.payment_reference,
                    pm.payment_method,
                    pm.amount_paid,
                    pm.payment_date,
                    pm.status,
                    pm.transaction_notes,
                    pm.created_at,
                    pm.updated_at
                FROM payments pm
                WHERE pm.payroll_id = %s
                ORDER BY pm.id DESC
                LIMIT 1;
            """
            return self.execute_query(query, (payroll_id,), fetch_one=True)
        except Exception as e:
            logger.error("Error fetching payment for payroll ID %s: %s", payroll_id, e)
            return None

    def get_by_reference(self, reference: str) -> Optional[Dict[str, Any]]:
        """Look up payment record by unique reference to prevent duplicates."""
        try:
            query = """
                SELECT id, payroll_id, payment_reference, status, amount_paid 
                FROM payments 
                WHERE payment_reference = %s
                LIMIT 1;
            """
            return self.execute_query(query, (reference.strip(),), fetch_one=True)
        except Exception as e:
            logger.error("Error checking payment reference '%s': %s", reference, e)
            return None

    def get_approved_payrolls_awaiting_payment(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all payroll statements in APPROVED status awaiting financial disbursement.
        Ordered by year DESC, month DESC, employee name ASC.
        """
        try:
            conditions = ["p.status = 'APPROVED'"]
            params = []

            if year:
                conditions.append("p.year = %s")
                params.append(year)
            if month:
                conditions.append("p.month = %s")
                params.append(month)

            where_clause = f"WHERE {' AND '.join(conditions)}"

            query = f"""
                SELECT 
                    p.id,
                    p.id AS payroll_id,
                    p.payroll_code,
                    p.employee_id,
                    p.year,
                    p.month,
                    p.gross_pay,
                    p.total_deductions,
                    p.net_pay,
                    p.generated_date,
                    p.status AS payroll_status,
                    p.remarks,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    CONCAT(e.first_name, ' ', e.last_name) AS full_name,
                    e.department,
                    e.designation,
                    e.email
                FROM payroll p
                JOIN employees e ON p.employee_id = e.id
                {where_clause}
                ORDER BY p.year DESC, p.month DESC, e.first_name ASC, e.last_name ASC;
            """
            rows = self.execute_query(query, tuple(params), fetch_all=True)
            return rows if rows else []
        except Exception as e:
            logger.error("Error fetching approved payrolls awaiting payment: %s", e)
            return []

    def get_paginated_payments(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        status: Optional[str] = None,
        method: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retrieve paginated payment history joined with employee and payroll details.
        Supports filtering by year, month, status, method, and text search.
        """
        try:
            page = max(1, page)
            per_page = max(1, min(100, per_page))
            offset = (page - 1) * per_page

            conditions = []
            params = []

            if year:
                conditions.append("p.year = %s")
                params.append(year)

            if month:
                conditions.append("p.month = %s")
                params.append(month)

            if status and status.upper() != "ALL":
                conditions.append("pm.status = %s")
                params.append(status.upper())

            if method and method.upper() != "ALL":
                conditions.append("pm.payment_method = %s")
                params.append(method.upper())

            if search and search.strip():
                s = f"%{search.strip()}%"
                conditions.append("""(
                    pm.payment_reference LIKE %s OR
                    p.payroll_code LIKE %s OR
                    e.employee_code LIKE %s OR
                    e.first_name LIKE %s OR
                    e.last_name LIKE %s OR
                    CONCAT(e.first_name, ' ', e.last_name) LIKE %s OR
                    e.department LIKE %s
                )""")
                params.extend([s, s, s, s, s, s, s])

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # 1. Total count query
            count_query = f"""
                SELECT COUNT(*) AS total 
                FROM payments pm
                JOIN payroll p ON pm.payroll_id = p.id
                JOIN employees e ON p.employee_id = e.id
                {where_clause};
            """
            count_res = self.execute_query(count_query, tuple(params), fetch_one=True)
            total_count = int(count_res.get("total", 0)) if count_res else 0

            # 2. Paginated data query
            data_query = f"""
                SELECT 
                    pm.id,
                    pm.id AS payment_id,
                    pm.payroll_id,
                    pm.payment_reference,
                    pm.payment_method,
                    pm.amount_paid,
                    pm.payment_date,
                    pm.status,
                    pm.transaction_notes,
                    pm.created_at,
                    p.payroll_code,
                    p.year,
                    p.month,
                    p.net_pay,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    CONCAT(e.first_name, ' ', e.last_name) AS full_name,
                    e.department
                FROM payments pm
                JOIN payroll p ON pm.payroll_id = p.id
                JOIN employees e ON p.employee_id = e.id
                {where_clause}
                ORDER BY pm.payment_date DESC, pm.id DESC
                LIMIT %s OFFSET %s;
            """
            data_params = tuple(params + [per_page, offset])
            rows = self.execute_query(data_query, data_params, fetch_all=True)

            return rows if rows else [], total_count
        except Exception as e:
            logger.error("Error fetching paginated payments: %s", e)
            return [], 0

    def record_payment_transaction(
        self,
        payroll_id: int,
        payment_reference: str,
        payment_method: str,
        amount_paid: Decimal,
        payment_date: Any,
        status: str = "SUCCESSFUL",
        transaction_notes: Optional[str] = None,
    ) -> int:
        """
        Record a payment disbursement within an ACID database transaction.
        
        Rules:
        - If status == 'SUCCESSFUL':
          Updates `payroll.status` to 'PAID' (with optimistic locking ensuring payroll was 'APPROVED').
        - If status != 'SUCCESSFUL' (e.g. FAILED, PENDING):
          Does NOT mark payroll as 'PAID'.
        
        Returns:
            Newly created payment record ID.
        """
        with self.transaction() as (cursor, conn):
            # 1. Insert into payments table
            insert_sql = """
                INSERT INTO payments (
                    payroll_id, payment_reference, payment_method,
                    amount_paid, payment_date, status, transaction_notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s);
            """
            cursor.execute(
                insert_sql,
                (
                    int(payroll_id),
                    payment_reference.strip(),
                    payment_method.upper(),
                    Decimal(str(amount_paid)),
                    payment_date,
                    status.upper(),
                    transaction_notes,
                ),
            )
            new_payment_id = cursor.lastrowid

            # 2. Update payroll status if payment was successful
            if status.upper() == "SUCCESSFUL":
                update_payroll_sql = """
                    UPDATE payroll 
                    SET status = 'PAID', 
                        payment_due_date = %s,
                        remarks = CONCAT(COALESCE(remarks, ''), '\nPaid ref: ', %s)
                    WHERE id = %s AND status = 'APPROVED';
                """
                cursor.execute(update_payroll_sql, (payment_date, payment_reference.strip(), int(payroll_id)))
                if cursor.rowcount == 0:
                    raise ValueError(
                        f"Payroll statement #{payroll_id} could not be marked as PAID. "
                        "It may have already been disbursed, cancelled, or modified concurrently."
                    )

            return new_payment_id

    def update_payment_status(
        self,
        payment_id: int,
        target_status: str,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Transition payment status with database transaction integrity.
        
        Workflows:
        - SUCCESSFUL -> REVERSED:
          Reverses payment and rolls back associated payroll from 'PAID' to 'APPROVED'.
        - PENDING -> SUCCESSFUL:
          Confirms pending payment and marks associated payroll as 'PAID'.
        - PENDING -> FAILED / REVERSED:
          Fails or reverses pending payment; payroll remains 'APPROVED'.
        """
        target_status = target_status.upper()

        with self.transaction() as (cursor, conn):
            # 1. Lock payment record for update
            cursor.execute("SELECT id, payroll_id, status FROM payments WHERE id = %s FOR UPDATE;", (payment_id,))
            payment_row = cursor.fetchone()
            if not payment_row:
                raise ValueError(f"Payment record #{payment_id} does not exist.")

            # Map tuple or dict if dictionary cursor
            if isinstance(payment_row, dict):
                current_status = payment_row["status"].upper()
                payroll_id = payment_row["payroll_id"]
            else:
                current_status = payment_row[2].upper()
                payroll_id = payment_row[1]

            if current_status == target_status:
                return True

            memo = f"\nStatus changed from {current_status} to {target_status}" + (f": {reason}" if reason else "")

            # 2. Update payments table
            cursor.execute(
                """
                UPDATE payments 
                SET status = %s,
                    transaction_notes = CONCAT(COALESCE(transaction_notes, ''), %s)
                WHERE id = %s;
                """,
                (target_status, memo, payment_id),
            )

            # 3. Handle payroll synchronization
            if current_status == "SUCCESSFUL" and target_status in ("REVERSED", "FAILED"):
                # Rollback payroll status from PAID back to APPROVED
                cursor.execute(
                    """
                    UPDATE payroll 
                    SET status = 'APPROVED',
                        remarks = CONCAT(COALESCE(remarks, ''), '\nPayment reversed: ', %s)
                    WHERE id = %s AND status = 'PAID';
                    """,
                    (reason or "Transaction reversal", payroll_id),
                )
            elif current_status in ("PENDING", "FAILED") and target_status == "SUCCESSFUL":
                # Confirm payment and advance payroll to PAID
                cursor.execute(
                    """
                    UPDATE payroll 
                    SET status = 'PAID',
                        remarks = CONCAT(COALESCE(remarks, ''), '\nPayment confirmed: ', %s)
                    WHERE id = %s AND status = 'APPROVED';
                    """,
                    (reason or "Payment confirmed", payroll_id),
                )
                if cursor.rowcount == 0:
                    raise ValueError(f"Associated payroll #{payroll_id} is not in APPROVED state.")

            return True

    def get_payment_summary(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> Dict[str, Any]:
        """Aggregate totals across all payment records or for selected period."""
        try:
            conditions = []
            params = []

            if year:
                conditions.append("p.year = %s")
                params.append(year)
            if month:
                conditions.append("p.month = %s")
                params.append(month)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT 
                    COUNT(*) AS total_records,
                    COALESCE(SUM(CASE WHEN pm.status = 'SUCCESSFUL' THEN pm.amount_paid ELSE 0 END), 0.00) AS total_disbursed,
                    COALESCE(SUM(CASE WHEN pm.status = 'SUCCESSFUL' THEN 1 ELSE 0 END), 0) AS successful_count,
                    COALESCE(SUM(CASE WHEN pm.status = 'PENDING' THEN 1 ELSE 0 END), 0) AS pending_count,
                    COALESCE(SUM(CASE WHEN pm.status = 'FAILED' THEN 1 ELSE 0 END), 0) AS failed_count,
                    COALESCE(SUM(CASE WHEN pm.status = 'REVERSED' THEN 1 ELSE 0 END), 0) AS reversed_count
                FROM payments pm
                JOIN payroll p ON pm.payroll_id = p.id
                {where_clause};
            """
            res = self.execute_query(query, tuple(params), fetch_one=True)
            if not res:
                return {
                    "total_records": 0,
                    "total_disbursed": Decimal("0.00"),
                    "successful_count": 0,
                    "pending_count": 0,
                    "failed_count": 0,
                    "reversed_count": 0,
                }
            return {
                "total_records": int(res.get("total_records", 0)),
                "total_disbursed": Decimal(str(res.get("total_disbursed", "0.00"))),
                "successful_count": int(res.get("successful_count", 0)),
                "pending_count": int(res.get("pending_count", 0)),
                "failed_count": int(res.get("failed_count", 0)),
                "reversed_count": int(res.get("reversed_count", 0)),
            }
        except Exception as e:
            logger.error("Error computing payment summary: %s", e)
            return {
                "total_records": 0,
                "total_disbursed": Decimal("0.00"),
                "successful_count": 0,
                "pending_count": 0,
                "failed_count": 0,
                "reversed_count": 0,
            }

    def get_available_years(self) -> List[int]:
        """Fetch distinct years present in payments/payroll."""
        from datetime import datetime
        current_year = datetime.now().year
        try:
            query = "SELECT DISTINCT p.year FROM payments pm JOIN payroll p ON pm.payroll_id = p.id ORDER BY p.year DESC;"
            rows = self.execute_query(query, fetch_all=True)
            years = [int(r["year"]) for r in rows if r and r.get("year")]
            if current_year not in years:
                years.append(current_year)
            return sorted(list(set(years)), reverse=True)
        except Exception as e:
            logger.warning("Error fetching payment years: %s", e)
            return [current_year, current_year - 1]
