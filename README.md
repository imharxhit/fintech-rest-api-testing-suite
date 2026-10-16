# fintech-rest-api-testing-suite

REST API functional, JSON schema contract, and SQLite database validation tests in Python.

## Overview

This repository provides an automated API testing suite designed for fintech service validation. It demonstrates contract testing, functional verification, and database state integrity testing using Python's requests, jsonschema, and sqlite3.

## API Endpoints Covered

- POST /api/v1/orders - Order creation and account debiting
- DELETE /api/v1/orders/{id} - Order cancellation and balance refunding

## Verification Capabilities

- HTTP Status Codes: Validates standard REST response codes including 200, 201, 400, 401, 409, and 422.
- JSON Schema Contracts: Strict schema validation ensuring response payloads adhere to field type and structural specifications.
- Idempotency Protection: Ensures header-based Idempotency-Key prevents duplicate transaction processing.
- Database Consistency: Direct SQLite database checks verifying user account balance debits upon order creation and full refunds upon cancellation.

## Running Tests

python -m unittest test_order_api.py -v
