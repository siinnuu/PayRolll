-- =============================================================================
-- Employee Payroll Management System - Seed Data (Module 1)
-- Database Name: employee_payroll
-- Note: Passwords are encrypted using Werkzeug secure password hashes (scrypt).
-- Default credentials for local development & testing:
--   admin / Admin@123
--   sarah.hr / User@123
--   michael.fin / User@123
-- =============================================================================

USE `employee_payroll`;

SET FOREIGN_KEY_CHECKS = 0;

-- Clean existing data for clean re-seeding
TRUNCATE TABLE `payments`;
TRUNCATE TABLE `payroll`;
TRUNCATE TABLE `attendance`;
TRUNCATE TABLE `salary_settings`;
TRUNCATE TABLE `employees`;
TRUNCATE TABLE `users`;

SET FOREIGN_KEY_CHECKS = 1;

-- -----------------------------------------------------------------------------
-- 1. Insert Users (No plaintext passwords!)
-- -----------------------------------------------------------------------------
INSERT INTO `users` (`id`, `username`, `email`, `password_hash`, `role`, `is_active`, `created_at`)
VALUES
(1, 'admin', 'admin@payroll.local', 'scrypt:32768:8:1$MM2nAICkKn87u0t2$843f778802918b48415acfb7fe90b7fde3cd5bc9a83683e0c67b25f35cd53a99ea4d21afac4db51bc120ebe80d9c4e5add0c4cf9477284d18bbf22a8a4eb2a17', 'ADMIN', TRUE, NOW()),
(2, 'sarah.hr', 'sarah.jenkins@example.com', 'scrypt:32768:8:1$AIeyw31uQ2eaD51L$7d52c8e64b6e22ac4c0bdbd888fbcdf0fab1d453fa1c42c0a86155942f70a6e0102c70a2e898ab63fbdff35748b432868ef9832b2e17677f80e6ae9e6554b904', 'HR', TRUE, NOW()),
(3, 'michael.fin', 'michael.chang@example.com', 'scrypt:32768:8:1$AIeyw31uQ2eaD51L$7d52c8e64b6e22ac4c0bdbd888fbcdf0fab1d453fa1c42c0a86155942f70a6e0102c70a2e898ab63fbdff35748b432868ef9832b2e17677f80e6ae9e6554b904', 'ACCOUNTANT', TRUE, NOW());

-- -----------------------------------------------------------------------------
-- 2. Insert Fictional Employees
-- -----------------------------------------------------------------------------
INSERT INTO `employees` (`id`, `employee_code`, `first_name`, `last_name`, `email`, `phone`, `department`, `designation`, `joining_date`, `status`, `user_id`, `created_at`)
VALUES
(1, 'EMP001', 'John', 'Doe', 'john.doe@example.com', '+1-555-0101', 'Engineering', 'Lead Software Engineer', '2023-01-15', 'ACTIVE', NULL, NOW()),
(2, 'EMP002', 'Sarah', 'Jenkins', 'sarah.jenkins@example.com', '+1-555-0102', 'Human Resources', 'HR Manager', '2023-03-01', 'ACTIVE', 2, NOW()),
(3, 'EMP003', 'Michael', 'Chang', 'michael.chang@example.com', '+1-555-0103', 'Finance', 'Senior Payroll Accountant', '2023-05-10', 'ACTIVE', 3, NOW());

-- -----------------------------------------------------------------------------
-- 3. Insert Salary Settings (DECIMAL monetary amounts)
-- -----------------------------------------------------------------------------
INSERT INTO `salary_settings` (`id`, `employee_id`, `base_salary`, `hourly_rate`, `hra`, `transport_allowance`, `medical_allowance`, `other_allowances`, `tax_deduction_rate`, `pf_deduction_rate`, `other_deductions`, `effective_from`, `created_at`)
VALUES
(1, 1, 85000.00, 48.85, 25500.00, 3000.00, 2500.00, 1500.00, 10.00, 12.00, 500.00, '2023-01-15', NOW()),
(2, 2, 65000.00, 37.35, 19500.00, 2500.00, 2000.00, 1000.00, 8.00, 12.00, 0.00, '2023-03-01', NOW()),
(3, 3, 75000.00, 43.10, 22500.00, 2500.00, 2500.00, 1200.00, 10.00, 12.00, 250.00, '2023-05-10', NOW());

-- -----------------------------------------------------------------------------
-- 4. Insert Sample Attendance Summaries (One per employee per month)
-- -----------------------------------------------------------------------------
INSERT INTO `attendance` (`id`, `employee_id`, `year`, `month`, `total_working_days`, `present_days`, `absent_days`, `paid_leaves`, `unpaid_leaves`, `overtime_hours`, `overtime_rate`, `notes`, `created_at`)
VALUES
(1, 1, 2026, 9, 30, 21.0, 0.0, 1.0, 0.0, 6.50, 48.85, 'Full month with 6.5 overtime hours', NOW()),
(2, 2, 2026, 9, 30, 21.0, 1.0, 0.0, 0.0, 0.00, 37.35, '1 absent day due to medical emergency', NOW()),
(3, 3, 2026, 9, 30, 20.0, 0.0, 2.0, 0.0, 4.00, 43.10, '2 approved paid leaves', NOW()),
(4, 1, 2026, 10, 31, 22.0, 0.0, 1.0, 0.0, 8.50, 48.85, 'Regular attendance with 8.5h OT', NOW()),
(5, 2, 2026, 10, 31, 21.0, 1.0, 1.0, 0.0, 0.00, 37.35, '1 casual leave taken', NOW()),
(6, 3, 2026, 10, 31, 20.5, 0.5, 2.0, 0.0, 4.00, 43.10, 'Half-day leave on Oct 14th', NOW());

-- -----------------------------------------------------------------------------
-- 5. Insert Sample Payroll Records (One main record per employee per month)
-- -----------------------------------------------------------------------------
INSERT INTO `payroll` (`id`, `payroll_code`, `employee_id`, `year`, `month`, `basic_pay`, `allowances_total`, `overtime_pay`, `gross_pay`, `leave_deduction`, `tax_deduction`, `pf_deduction`, `other_deductions`, `total_deductions`, `net_pay`, `status`, `generated_date`, `payment_due_date`, `remarks`, `created_at`)
VALUES
(1, 'PAY-2026-09-EMP001', 1, 2026, 9, 85000.00, 32500.00, 476.29, 117976.29, 0.00, 11797.63, 10200.00, 500.00, 22497.63, 95478.66, 'PAID', '2026-09-30', '2026-10-05', 'September 2026 Salary Processed', NOW()),
(2, 'PAY-2026-09-EMP002', 2, 2026, 9, 65000.00, 25000.00, 0.00, 90000.00, 0.00, 7200.00, 7800.00, 0.00, 15000.00, 75000.00, 'PAID', '2026-09-30', '2026-10-05', 'September 2026 Salary Processed', NOW()),
(3, 'PAY-2026-09-EMP003', 3, 2026, 9, 75000.00, 28700.00, 258.60, 103958.60, 0.00, 10395.86, 9000.00, 250.00, 19645.86, 84312.74, 'PAID', '2026-09-30', '2026-10-05', 'September 2026 Salary Processed', NOW());

-- -----------------------------------------------------------------------------
-- 6. Insert Sample Payments (Linked to Payroll)
-- -----------------------------------------------------------------------------
INSERT INTO `payments` (`id`, `payroll_id`, `payment_reference`, `payment_method`, `amount_paid`, `payment_date`, `status`, `transaction_notes`, `created_at`)
VALUES
(1, 1, 'TXN-202609-001', 'BANK_TRANSFER', 95478.66, '2026-10-02', 'SUCCESSFUL', 'Direct deposit to employee bank account ending in 4128', NOW()),
(2, 2, 'TXN-202609-002', 'BANK_TRANSFER', 75000.00, '2026-10-02', 'SUCCESSFUL', 'Direct deposit to employee bank account ending in 8892', NOW()),
(3, 3, 'TXN-202609-003', 'BANK_TRANSFER', 84312.74, '2026-10-02', 'SUCCESSFUL', 'Direct deposit to employee bank account ending in 5510', NOW());
