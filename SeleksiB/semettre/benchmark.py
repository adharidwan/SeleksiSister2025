#!/usr/bin/env python3
import subprocess
import sys
import time
import os
import random
from pathlib import Path
from datetime import datetime

# Increase the limit for integer string conversion
sys.set_int_max_str_digits(2000000)  # Handle up to 1,000,000-digit numbers

def generate_random_number(digits):
    """Generate a random number as a string with specified digits"""
    print(f"Generating {digits}-digit number...")
    num = str(random.randint(1, 9))
    for _ in range(digits - 1):
        num += str(random.randint(0, 9))
    return num

def run_test(num1, num2, description="", timeout=30):
    """Run a test case, verify the result, and log to file with full digits"""
    output_lines = []
    file_output_lines = []
    output_lines.append(f"\n{'='*60}")
    output_lines.append(f"TEST: {description}")
    output_lines.append(f"Input 1 ({len(num1)} digits): {num1[:50]}{'...' if len(num1) > 50 else ''}")
    output_lines.append(f"Input 2 ({len(num2)} digits): {num2[:50]}{'...' if len(num2) > 50 else ''}")
    output_lines.append(f"{'='*60}")
    
    # For file: write full numbers
    file_output_lines.append(f"\n{'='*60}")
    file_output_lines.append(f"TEST: {description}")
    file_output_lines.append(f"Input 1 ({len(num1)} digits): {num1}")
    file_output_lines.append(f"Input 2 ({len(num2)} digits): {num2}")
    file_output_lines.append(f"{'='*60}")
    
    print(f"Computing expected result for {description}...")
    expected = str(int(num1) * int(num2))
    output_lines.append(f"Expected ({len(expected)} digits): {expected[:50]}{'...' if len(expected) > 50 else ''}")
    output_lines.append(f"Expected (last 50 digits): ...{expected[-50:]}")
    file_output_lines.append(f"Expected ({len(expected)} digits): {expected}")
    file_output_lines.append(f"Expected (last 50 digits): ...{expected[-50:]}")
    
    try:
        print(f"Running C program for {description}...")
        start_time = time.time()
        process = subprocess.run(
            ['./main'],
            input=f"{num1} {num2}",
            text=True,
            capture_output=True,
            timeout=timeout
        )
        end_time = time.time()
        
        if process.returncode != 0:
            output_lines.append(f"❌ FAILED: Program crashed with return code {process.returncode}")
            output_lines.append(f"stderr: {process.stderr}")
            file_output_lines.append(f"❌ FAILED: Program crashed with return code {process.returncode}")
            file_output_lines.append(f"stderr: {process.stderr}")
            for line in output_lines:
                print(line)
            write_to_file(file_output_lines)
            return False
            
        actual = process.stdout.strip()
        execution_time = end_time - start_time
        
        output_lines.append(f"Actual   ({len(actual)} digits): {actual[:50]}{'...' if len(actual) > 50 else ''}")
        output_lines.append(f"Actual   (last 50 digits): ...{actual[-50:]}")
        output_lines.append(f"Time: {execution_time:.3f}s")
        file_output_lines.append(f"Actual   ({len(actual)} digits): {actual}")
        file_output_lines.append(f"Actual   (last 50 digits): ...{actual[-50:]}")
        file_output_lines.append(f"Time: {execution_time:.3f}s")
        
        if actual == expected:
            output_lines.append("✅ PASSED")
            file_output_lines.append("✅ PASSED")
            result = True
        else:
            output_lines.append("❌ FAILED: Results don't match")
            file_output_lines.append("❌ FAILED: Results don't match")
            min_len = min(len(expected), len(actual))
            for i in range(min_len):
                if expected[i] != actual[i]:
                    output_lines.append(f"First difference at position {i}: expected '{expected[i]}', got '{actual[i]}'")
                    file_output_lines.append(f"First difference at position {i}: expected '{expected[i]}', got '{actual[i]}'")
                    break
            result = False
            
        for line in output_lines:
            print(line)
        write_to_file(file_output_lines)
        return result
            
    except subprocess.TimeoutExpired:
        output_lines.append(f"❌ FAILED: Timeout after {timeout}s")
        file_output_lines.append(f"❌ FAILED: Timeout after {timeout}s")
        for line in output_lines:
            print(line)
        write_to_file(file_output_lines)
        return False
    except Exception as e:
        output_lines.append(f"❌ FAILED: Exception - {e}")
        file_output_lines.append(f"❌ FAILED: Exception - {e}")
        for line in output_lines:
            print(line)
        write_to_file(file_output_lines)
        return False

def write_to_file(lines):
    """Write test output to a timestamped .txt file with full digits"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"test_results_{timestamp}.txt"
    with open(output_file, 'a') as f:
        for line in lines:
            f.write(line + '\n')

def main():
    seed = int(time.time())
    print(f"Random seed: {seed}")
    random.seed(seed)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"test_results_{timestamp}.txt", 'w') as f:
        f.write(f"Test Results (Seed: {seed})\n")
        f.write(f"{'='*60}\n")
        f.write("WARNING: Writing full digits for large numbers may cause significant I/O delays.\n")
    
    print("WARNING: Writing full digits to file for large numbers may cause delays.")
    
    if not os.path.exists('./main'):
        error_msg = ["❌ Error: ./main not found. Please compile your code first:",
                     "gcc -o main your_code.c -O2"]
        for line in error_msg:
            print(line)
        with open(f"test_results_{timestamp}.txt", 'a') as f:
            for line in error_msg:
                f.write(line + '\n')
        sys.exit(1)
    
    test_results = []
    
    test_results.append(run_test(
        "999999999999999999",
        "888888888888888888", 
        "Basic 18-digit multiplication"
    ))
    
    test_results.append(run_test("7", "8", "Single digit multiplication"))
    test_results.append(run_test("123", "456", "3-digit multiplication"))
    
    test_results.append(run_test("0", "123456789", "Zero multiplication"))
    test_results.append(run_test("123456789", "0", "Multiplication by zero"))
    
    test_results.append(run_test(
        "1000000000000000000000000000000",
        "1000000000000000000000000000000",
        "Powers of 10 (30 digits each)"
    ))
    
    num1_32 = generate_random_number(32)
    num2_32 = generate_random_number(32)
    test_results.append(run_test(num1_32, num2_32, "32 Digits"))
    
    num1_64 = generate_random_number(64)
    num2_64 = generate_random_number(64)
    test_results.append(run_test(num1_64, num2_64, "64 Digits"))
    
    num1_100 = generate_random_number(100)
    num2_100 = generate_random_number(100)
    test_results.append(run_test(num1_100, num2_100, "100 Digits"))
    
    num1_500 = generate_random_number(500)
    num2_500 = generate_random_number(500)
    test_results.append(run_test(
        num1_500, num2_500, 
        "500 Digits", 
        timeout=60
    ))
    
    num1_1000 = generate_random_number(1000)
    num2_1000 = generate_random_number(1000)
    test_results.append(run_test(
        num1_1000, num2_1000,
        "1000 Digits",
        timeout=120
    ))
    
    num1_5000 = generate_random_number(5000)
    num2_5000 = generate_random_number(5000)
    test_results.append(run_test(
        num1_5000, num2_5000,
        "5000 Digits",
        timeout=300
    ))
    
    test_results.append(run_test(
        "123456789012345678901234567890",
        "987",
        "Different sizes (30 vs 3 digits)"
    ))
    
    test_results.append(run_test(
        "123454321",
        "987656789",
        "Palindromic numbers"
    ))
    
    summary_lines = []
    file_summary_lines = []
    summary_lines.append(f"\n{'='*60}")
    summary_lines.append("SUMMARY")
    summary_lines.append(f"{'='*60}")
    file_summary_lines.append(f"\n{'='*60}")
    file_summary_lines.append("SUMMARY")
    file_summary_lines.append(f"{'='*60}")
    
    passed = sum(test_results)
    total = len(test_results)
    
    summary_lines.append(f"Tests passed: {passed}/{total}")
    summary_lines.append(f"Success rate: {passed/total*100:.1f}%")
    file_summary_lines.append(f"Tests passed: {passed}/{total}")
    file_summary_lines.append(f"Success rate: {passed/total*100:.1f}%")
    
    if passed == total:
        summary_lines.append("🎉 ALL TESTS PASSED!")
        summary_lines.append("\nEstimated scoring:")
        summary_lines.append("✅ 1 point  - Basic functionality (2^32 range)")
        summary_lines.append("✅ 5 points - Large numbers (10^1000 digits)")
        file_summary_lines.append("🎉 ALL TESTS PASSED!")
        file_summary_lines.append("\nEstimated scoring:")
        file_summary_lines.append("✅ 1 point  - Basic functionality (2^32 range)")
        file_summary_lines.append("✅ 5 points - Large numbers (10^1000 digits)")
        if any("5000 digits" in str(i) for i in range(len(test_results)) if test_results[i]):
            summary_lines.append("✅ 8 points - Very large numbers (toward 10^1000000)")
            file_summary_lines.append("✅ 8 points - Very large numbers (toward 10^1000000)")
        else:
            summary_lines.append("❓ 8 points - Need to test even larger numbers for full points")
            file_summary_lines.append("❓ 8 points - Need to test even larger numbers for full points")
    else:
        summary_lines.append(f"❌ {total - passed} tests failed. Check implementation.")
        file_summary_lines.append(f"❌ {total - passed} tests failed. Check implementation.")
        
    summary_lines.append(f"\nFor 8-point tier, try testing with 50,000+ digit numbers:")
    summary_lines.append("python3 verify.py --extreme")
    file_summary_lines.append(f"\nFor 8-point tier, try testing with 50,000+ digit numbers:")
    file_summary_lines.append("python3 verify.py --extreme")
    
    for line in summary_lines:
        print(line)
    write_to_file(file_summary_lines)

def run_extreme_tests(skip_million=False):
    """Run extreme tests for 8-point tier"""
    print("Running extreme tests for 8-point tier...")
    
    seed = int(time.time())
    print(f"Random seed: {seed}")
    random.seed(seed)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"test_results_{timestamp}.txt", 'w') as f:
        f.write(f"Extreme Test Results (Seed: {seed})\n")
        f.write(f"{'='*60}\n")
        f.write("WARNING: Writing full digits for large numbers may cause significant I/O delays.\n")
    
    print("WARNING: Writing full digits to file for large numbers may cause delays.")
    
    num1_10k = generate_random_number(10000)
    num2_10k = generate_random_number(10000)
    run_test(num1_10k, num2_10k, "10,000 digits 1", timeout=600)
    
    num1_10k_alt = generate_random_number(10000)
    num2_10k_alt = generate_random_number(10000)
    run_test(num1_10k_alt, num2_10k_alt, "10,000 digits 2", timeout=600)
    
    num1_50k = generate_random_number(50000)
    num2_50k = generate_random_number(50000)
    run_test(num1_50k, num2_50k, "50,000 digits", timeout=1200)
    
    if not skip_million:
        num1_1m = generate_random_number(1000000)
        num2_1m = generate_random_number(1000000)
        run_test(num1_1m, num2_1m, "1,000,000 digits", timeout=3600)

def run_hell_tests():
    """Run hell tests for 8-point tier"""
    print("Running hell tests for 8-point tier...")
    
    seed = int(time.time())
    print(f"Random seed: {seed}")
    random.seed(seed)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"test_results_{timestamp}.txt", 'w') as f:
        f.write(f"Hell Test Results (Seed: {seed})\n")
        f.write(f"{'='*60}\n")
        f.write("WARNING: Writing full digits for large numbers may cause significant I/O delays.\n")
    
    print("WARNING: Writing full digits to file for large numbers may cause delays.")
    
    for _ in range(10):
        num1 = generate_random_number(1000000)
        num2 = generate_random_number(1000000)
        run_test(num1, num2, "Hell test - 1,000,000 digits", timeout=3600)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--extreme":
        skip_million = "--skip-million" in sys.argv
        run_extreme_tests(skip_million=skip_million)
    elif len(sys.argv) > 1 and sys.argv[1] == "--hell":
        run_hell_tests()
    else:
        main()