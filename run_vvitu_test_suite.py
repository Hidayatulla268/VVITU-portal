"""
VVITU Academic Portal — Master 9-Tier Test Suite Orchestrator & Dashboard Reporter
Executes all 9 tiers sequentially, measures latency, captures outcomes,
and renders the executive test report matching the university test hierarchy.
"""

import os
import sys
import time

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')

import django
django.setup()

from django.test.runner import DiscoverRunner


TIERS = [
    ("Tier 1", "Unit Testing",         "tests.test_01_unit"),
    ("Tier 2", "Integration Testing",  "tests.test_02_integration"),
    ("Tier 3", "Functional Testing",   "tests.test_03_functional"),
    ("Tier 4", "System Testing",       "tests.test_04_system"),
    ("Tier 5", "Security Testing",     "tests.test_05_security"),
    ("Tier 6", "Performance Testing",  "tests.test_06_performance"),
    ("Tier 7", "Compatibility Testing", "tests.test_07_compatibility"),
    ("Tier 8", "Regression Testing",   "tests.test_08_regression"),
    ("Tier 9", "UAT",                  "tests.test_09_uat"),
    ("Tier 10", "Enterprise Audit",    "tests.test_10_issue_audit"),
]


def run_master_suite():
    print("=" * 78)
    print("       VVITU ACADEMIC PORTAL — COMPLETE 10-TIER ENTERPRISE TEST SUITE")
    print("=" * 78)
    print("Initializing isolated Django test database...")

    runner = DiscoverRunner(verbosity=1, interactive=False)
    old_config = runner.setup_databases()

    tier_results = []
    total_start = time.time()
    grand_total_tests = 0
    grand_total_failures = 0
    grand_total_errors = 0

    try:
        for tier_code, tier_name, test_label in TIERS:
            print(f"\n[RUNNING] {tier_code}: {tier_name} ({test_label})...")
            suite = runner.build_suite([test_label])
            suite_tests_count = suite.countTestCases()
            grand_total_tests += suite_tests_count

            tier_start = time.time()
            result = runner.run_suite(suite)
            tier_duration = time.time() - tier_start

            failures_count = len(result.failures)
            errors_count = len(result.errors)
            grand_total_failures += failures_count
            grand_total_errors += errors_count

            passed = (failures_count == 0 and errors_count == 0)
            status_text = "PASS" if passed else "FAIL"

            tier_results.append({
                'code': tier_code,
                'name': tier_name,
                'tests': suite_tests_count,
                'failures': failures_count,
                'errors': errors_count,
                'duration': tier_duration,
                'passed': passed,
            })
            print(f"[{status_text}] {tier_name}: {suite_tests_count} tests run in {tier_duration:.2f}s (Failures={failures_count}, Errors={errors_count})")

    finally:
        print("\nTearing down test database...")
        runner.teardown_databases(old_config)

    total_duration = time.time() - total_start

    # Render Final Hierarchy Dashboard
    print("\n" + "=" * 78)
    print("                        TEST EXECUTION SUMMARY DASHBOARD")
    print("=" * 78)

    hierarchy = """
                          VVITU PORTAL
                               |
                               v
                      +-----------------+
                      | Unit Testing    |  [{t1_status}] {t1_tests} Tests ({t1_time:.2f}s)
                      +--------+--------+
                               |
                               v
                      +-----------------+
                      | Integration     |  [{t2_status}] {t2_tests} Tests ({t2_time:.2f}s)
                      | Testing         |
                      +--------+--------+
                               |
                               v
                      +-----------------+
                      | Functional      |  [{t3_status}] {t3_tests} Tests ({t3_time:.2f}s)
                      | Testing         |
                      +--------+--------+
                               |
                               v
                      +-----------------+
                      | System Testing  |  [{t4_status}] {t4_tests} Tests ({t4_time:.2f}s)
                      +--------+--------+
                               |
                               v
                      +-----------------+
                      | Security        |  [{t5_status}] {t5_tests} Tests ({t5_time:.2f}s)
                      | Testing         |
                      +--------+--------+
                               |
                               v
                      +-----------------+
                      | Performance     |  [{t6_status}] {t6_tests} Tests ({t6_time:.2f}s)
                      +--------+--------+
                               |
                               v
                      +-----------------+
                      | Compatibility   |  [{t7_status}] {t7_tests} Tests ({t7_time:.2f}s)
                      +--------+--------+
                               |
                               v
                      +-----------------+
                      | Regression      |  [{t8_status}] {t8_tests} Tests ({t8_time:.2f}s)
                      +--------+--------+
                               |
                               v
                      +-----------------+
                      | UAT             |  [{t9_status}] {t9_tests} Tests ({t9_time:.2f}s)
                      +--------+--------+
                               |
                               v
                      +-----------------+
                      | Enterprise      |  [{t10_status}] {t10_tests} Tests ({t10_time:.2f}s)
                      | Issue Audit     |
                      +-----------------+
    """.format(
        t1_status="PASS" if tier_results[0]['passed'] else "FAIL", t1_tests=tier_results[0]['tests'], t1_time=tier_results[0]['duration'],
        t2_status="PASS" if tier_results[1]['passed'] else "FAIL", t2_tests=tier_results[1]['tests'], t2_time=tier_results[1]['duration'],
        t3_status="PASS" if tier_results[2]['passed'] else "FAIL", t3_tests=tier_results[2]['tests'], t3_time=tier_results[2]['duration'],
        t4_status="PASS" if tier_results[3]['passed'] else "FAIL", t4_tests=tier_results[3]['tests'], t4_time=tier_results[3]['duration'],
        t5_status="PASS" if tier_results[4]['passed'] else "FAIL", t5_tests=tier_results[4]['tests'], t5_time=tier_results[4]['duration'],
        t6_status="PASS" if tier_results[5]['passed'] else "FAIL", t6_tests=tier_results[5]['tests'], t6_time=tier_results[5]['duration'],
        t7_status="PASS" if tier_results[6]['passed'] else "FAIL", t7_tests=tier_results[6]['tests'], t7_time=tier_results[6]['duration'],
        t8_status="PASS" if tier_results[7]['passed'] else "FAIL", t8_tests=tier_results[7]['tests'], t8_time=tier_results[7]['duration'],
        t9_status="PASS" if tier_results[8]['passed'] else "FAIL", t9_tests=tier_results[8]['tests'], t9_time=tier_results[8]['duration'],
        t10_status="PASS" if tier_results[9]['passed'] else "FAIL", t10_tests=tier_results[9]['tests'], t10_time=tier_results[9]['duration'],
    )
    print(hierarchy)
    print("-" * 78)
    print(f"TOTAL TESTS EXECUTED : {grand_total_tests}")
    print(f"PASSED               : {grand_total_tests - grand_total_failures - grand_total_errors}")
    print(f"FAILED / ERRORS      : {grand_total_failures + grand_total_errors}")
    print(f"TOTAL DURATION       : {total_duration:.2f} seconds")
    print(f"OVERALL RESULT       : {'ALL TIERS PASSED (100% SUCCESS)' if (grand_total_failures == 0 and grand_total_errors == 0) else 'FAILURES DETECTED'}")
    print("=" * 78)

    return 0 if (grand_total_failures == 0 and grand_total_errors == 0) else 1


if __name__ == '__main__':
    sys.exit(run_master_suite())
