#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test runner script for the Boilerplate project with empirical performance-based test management.

.DESCRIPTION
    Provides convenient commands for running different test suites based on empirical performance data:
    - fast: Run fast tests only (excludes slow tests, default behavior, runs in parallel)
    - slow: Run slow tests only (performance-intensive template operations)
    - integration: Run all integration tests (both fast and slow)
    - all: Run all tests including slow ones
    - benchmark: Run all tests with detailed duration reporting for performance analysis

.PARAMETER Mode
    The type of tests to run based on performance characteristics and test scope

.EXAMPLE
    .\test-runner.ps1 fast
    .\test-runner.ps1 slow
    .\test-runner.ps1 benchmark
#>

param(
    [ValidateSet("fast", "slow", "integration", "all", "benchmark")]
    [string]$Mode = "fast"
)

Push-Location $PSScriptRoot\..

try {
    switch ($Mode) {
        "fast" {
            Write-Host "Running fast tests..." -ForegroundColor Green
            uv run pytest
        }
        "slow" {
            Write-Host "Running slow tests..." -ForegroundColor Red
            uv run pytest -m slow
        }
        "integration" {
            Write-Host "Running integration tests..." -ForegroundColor Blue
            uv run pytest tests/integration/
        }
        "all" {
            Write-Host "Running all tests..." -ForegroundColor Yellow
            uv run pytest -m ""
        }
        "benchmark" {
            Write-Host "Running tests with performance analysis..." -ForegroundColor Cyan
            uv run pytest -m "" --durations=0
        }
        default {
            Write-Error "Invalid mode: $Mode"
            exit 1
        }
    }
} finally {
    Pop-Location
}
