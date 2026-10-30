-- =============================================================================
-- Employee Payroll Management System - Database Schema (Module 1)
-- Database Name: employee_payroll
-- Engine: InnoDB
-- Charset: utf8mb4
-- Collation: utf8mb4_unicode_ci
-- =============================================================================

CREATE DATABASE IF NOT EXISTS `employee_payroll`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `employee_payroll`;

-- Disable foreign key checks during schema creation/reset if needed
SET FOREIGN_KEY_CHECKS = 0;

-- -----------------------------------------------------------------------------
-- 1. Table: users
-- Description: System authentication and role-based access accounts
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `username` VARCHAR(50) NOT NULL,
    `email` VARCHAR(100) NOT NULL,
    `password_hash` VARCHAR(255) NOT NULL,
    `role` ENUM('ADMIN', 'HR', 'ACCOUNTANT', 'EMPLOYEE') NOT NULL DEFAULT 'HR',
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_users_username` (`username`),
    UNIQUE KEY `uq_users_email` (`email`),
    INDEX `idx_users_role` (`role`),
    INDEX `idx_users_is_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 2. Table: employees
-- Description: Employee profiles and organizational positioning
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS `employees`;
CREATE TABLE `employees` (
    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `employee_code` VARCHAR(20) NOT NULL,
    `first_name` VARCHAR(50) NOT NULL,
    `last_name` VARCHAR(50) NOT NULL,
    `email` VARCHAR(100) NOT NULL,
    `phone` VARCHAR(20) NULL,
    `department` VARCHAR(50) NOT NULL,
    `designation` VARCHAR(50) NOT NULL,
    `joining_date` DATE NOT NULL,
    `status` ENUM('ACTIVE', 'INACTIVE', 'TERMINATED', 'ON_LEAVE') NOT NULL DEFAULT 'ACTIVE',
    `user_id` INT UNSIGNED NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_employees_code` (`employee_code`),
    UNIQUE KEY `uq_employees_email` (`email`),
    UNIQUE KEY `uq_employees_user_id` (`user_id`),
    INDEX `idx_employees_status` (`status`),
    INDEX `idx_employees_department` (`department`),
    INDEX `idx_employees_name` (`last_name`, `first_name`),
    CONSTRAINT `fk_employees_user`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 3. Table: salary_settings
-- Description: Base salary structures, allowances, and statutory deduction rates
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS `salary_settings`;
CREATE TABLE `salary_settings` (
    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `employee_id` INT UNSIGNED NOT NULL,
    `base_salary` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `hourly_rate` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `hra` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `transport_allowance` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `medical_allowance` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `other_allowances` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `tax_deduction_rate` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    `pf_deduction_rate` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    `other_deductions` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `effective_from` DATE NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_salary_settings_employee` (`employee_id`),
    INDEX `idx_salary_settings_employee` (`employee_id`),
    CONSTRAINT `fk_salary_settings_employee`
        FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 4. Table: attendance
-- Description: Monthly attendance summaries per employee (one record per month)
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS `attendance`;
CREATE TABLE `attendance` (
    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `employee_id` INT UNSIGNED NOT NULL,
    `year` SMALLINT UNSIGNED NOT NULL,
    `month` TINYINT UNSIGNED NOT NULL,
    `total_working_days` TINYINT UNSIGNED NOT NULL DEFAULT 30,
    `present_days` DECIMAL(4,1) NOT NULL DEFAULT 0.0,
    `absent_days` DECIMAL(4,1) NOT NULL DEFAULT 0.0,
    `paid_leaves` DECIMAL(4,1) NOT NULL DEFAULT 0.0,
    `unpaid_leaves` DECIMAL(4,1) NOT NULL DEFAULT 0.0,
    `overtime_hours` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    `overtime_rate` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    `notes` VARCHAR(255) NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_attendance_employee_month_year` (`employee_id`, `year`, `month`),
    INDEX `idx_attendance_period` (`year`, `month`),
    INDEX `idx_attendance_employee` (`employee_id`),
    CONSTRAINT `chk_attendance_month` CHECK (`month` BETWEEN 1 AND 12),
    CONSTRAINT `chk_attendance_working_days` CHECK (`total_working_days` > 0),
    CONSTRAINT `fk_attendance_employee`
        FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 5. Table: payroll
-- Description: Monthly payroll records (one main payroll record per employee per month)
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS `payroll`;
CREATE TABLE `payroll` (
    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `payroll_code` VARCHAR(40) NOT NULL,
    `employee_id` INT UNSIGNED NOT NULL,
    `year` SMALLINT UNSIGNED NOT NULL,
    `month` TINYINT UNSIGNED NOT NULL,
    `basic_pay` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `allowances_total` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `overtime_pay` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `gross_pay` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `leave_deduction` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `tax_deduction` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `pf_deduction` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `other_deductions` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `total_deductions` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `net_pay` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    `status` ENUM('DRAFT', 'GENERATED', 'APPROVED', 'PAID', 'CANCELLED') NOT NULL DEFAULT 'DRAFT',
    `generated_date` DATE NOT NULL,
    `payment_due_date` DATE NULL,
    `remarks` TEXT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_payroll_code` (`payroll_code`),
    UNIQUE KEY `uq_payroll_employee_month_year` (`employee_id`, `year`, `month`),
    INDEX `idx_payroll_period` (`year`, `month`),
    INDEX `idx_payroll_status` (`status`),
    INDEX `idx_payroll_employee` (`employee_id`),
    CONSTRAINT `chk_payroll_month` CHECK (`month` BETWEEN 1 AND 12),
    CONSTRAINT `fk_payroll_employee`
        FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 6. Table: payments
-- Description: Payment disbursement records linked to payroll statements
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS `payments`;
CREATE TABLE `payments` (
    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `payroll_id` INT UNSIGNED NOT NULL,
    `payment_reference` VARCHAR(60) NOT NULL,
    `payment_method` ENUM('BANK_TRANSFER', 'CASH', 'CHEQUE', 'UPI', 'DIRECT_DEPOSIT') NOT NULL DEFAULT 'BANK_TRANSFER',
    `amount_paid` DECIMAL(12,2) NOT NULL,
    `payment_date` DATE NOT NULL,
    `status` ENUM('PENDING', 'SUCCESSFUL', 'FAILED', 'REVERSED') NOT NULL DEFAULT 'SUCCESSFUL',
    `transaction_notes` TEXT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_payments_reference` (`payment_reference`),
    INDEX `idx_payments_payroll` (`payroll_id`),
    INDEX `idx_payments_date` (`payment_date`),
    INDEX `idx_payments_status` (`status`),
    CONSTRAINT `fk_payments_payroll`
        FOREIGN KEY (`payroll_id`) REFERENCES `payroll` (`id`)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;
