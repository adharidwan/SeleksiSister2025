#!/usr/bin/env python3
import subprocess
import sys
import time
import os
import random
from pathlib import Path

# Increase the limit for integer string conversion
sys.set_int_max_str_digits(2000000)  # Handle up to 1,000,000-digit numbers

def generate_random_number(digits):
    """Generate a random number as a string with specified digits"""
    # Start with a non-zero digit to avoid leading zeros
    num = str(random.randint(1, 9))
    # Add remaining random digits
    for _ in range(digits - 1):
        num += str(random.randint(0, 9))
    return num

def run_test(num1, num2, description="", timeout=30):
    """Run a test case and verify the result"""
    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print(f"Input 1 ({len(num1)} digits): {num1[:50]}{'...' if len(num1) > 50 else ''}")
    print(f"Input 2 ({len(num2)} digits): {num2[:50]}{'...' if len(num2) > 50 else ''}")
    print(f"{'='*60}")
    
    expected = str(int(num1) * int(num2))
    print(f"Expected ({len(expected)} digits): {expected[:50]}{'...' if len(expected) > 50 else ''}")
    print(f"Expected (last 50 digits): ...{expected[-50:]}")
    
    try:
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
            print(f"❌ FAILED: Program crashed with return code {process.returncode}")
            print(f"stderr: {process.stderr}")
            return False
            
        actual = process.stdout.strip()
        execution_time = end_time - start_time
        
        print(f"Actual   ({len(actual)} digits): {actual[:50]}{'...' if len(actual) > 50 else ''}")
        print(f"Actual   (last 50 digits): ...{actual[-50:]}")
        print(f"Time: {execution_time:.3f}s")
        
        if actual == expected:
            print("✅ PASSED")
            return True
        else:
            print("❌ FAILED: Results don't match")
            # Show where they differ
            min_len = min(len(expected), len(actual))
            for i in range(min_len):
                if expected[i] != actual[i]:
                    print(f"First difference at position {i}: expected '{expected[i]}', got '{actual[i]}'")
                    break
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ FAILED: Timeout after {timeout}s")
        return False
    except Exception as e:
        print(f"❌ FAILED: Exception - {e}")
        return False

def main():
    seed = int(time.time())
    print(f"Random seed: {seed}")
    random.seed(seed)

    if not os.path.exists('./main'):
        print("❌ Error: ./main not found. Please compile your code first:")
        print("gcc -o main your_code.c -O2")
        sys.exit(1)
    
    test_results = []
    
    # Test 1: Basic functionality
    test_results.append(run_test(
        "999999999999999999",
        "888888888888888888", 
        "Basic 18-digit multiplication"
    ))
    
    # Test 2: Small numbers
    test_results.append(run_test("7", "8", "Single digit multiplication"))
    test_results.append(run_test("123", "456", "3-digit multiplication"))
    
    # Test 3: Zero cases
    test_results.append(run_test("0", "123456789", "Zero multiplication"))
    test_results.append(run_test("123456789", "0", "Multiplication by zero"))
    
    # Test 4: Powers of 10
    test_results.append(run_test(
        "1000000000000000000000000000000",
        "1000000000000000000000000000000",
        "Powers of 10 (30 digits each)"
    ))
    
    # Test 5: Medium size numbers (32 digits each)
    num1_32 = generate_random_number(32)
    num2_32 = generate_random_number(32)
    test_results.append(run_test(num1_32, num2_32, "32 Digits"))
    
    # Test 6: Large numbers (64 digits each)
    num1_64 = generate_random_number(64)
    num2_64 = generate_random_number(64)
    test_results.append(run_test(num1_64, num2_64, "64 Digits"))
    
    # Test 7: Very large numbers (100 digits each)
    num1_100 = generate_random_number(100)
    num2_100 = generate_random_number(100)
    test_results.append(run_test(num1_100, num2_100, "100 Digits"))
    
    # Test 8: Huge numbers (500 digits each)
    num1_500 = generate_random_number(500)
    num2_500 = generate_random_number(500)
    test_results.append(run_test(
        num1_500, num2_500, 
        "500 Digits", 
        timeout=60
    ))
    
    # Test 9: Extreme numbers (1000 digits each) - For 5-point tier
    num1_1000 = generate_random_number(1000)
    num2_1000 = generate_random_number(1000)
    test_results.append(run_test(
        num1_1000, num2_1000,
        "1000 Digits",
        timeout=120
    ))
    
    # Test 10: Maximum numbers (5000 digits each) - Pushing toward 8-point tier
    num1_5000 = generate_random_number(5000)
    num2_5000 = generate_random_number(5000)
    test_results.append(run_test(
        num1_5000, num2_5000,
        "5000 Digits",
        timeout=300
    ))
    
    # Test 11: Edge case - Different sizes
    test_results.append(run_test(
        "123456789012345678901234567890",
        "987",
        "Different sizes (30 vs 3 digits)"
    ))
    
    # Test 12: Palindromic numbers
    test_results.append(run_test(
        "123454321",
        "987656789",
        "Palindromic numbers"
    ))
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"Tests passed: {passed}/{total}")
    print(f"Success rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("\nEstimated scoring:")
        print("✅ 1 point  - Basic functionality (2^32 range)")
        print("✅ 5 points - Large numbers (10^1000 digits)")
        if any("5000 digits" in str(i) for i in range(len(test_results)) if test_results[i]):
            print("✅ 8 points - Very large numbers (toward 10^1000000)")
        else:
            print("❓ 8 points - Need to test even larger numbers for full points")
    else:
        print(f"❌ {total - passed} tests failed. Check implementation.")
        
    print(f"\nFor 8-point tier, try testing with 50,000+ digit numbers:")
    print("python3 verify.py --extreme")

def run_extreme_tests():
    """Run extreme tests for 8-point tier"""
    print("Running extreme tests for 8-point tier...")
    
    # Set random seed for reproducibility
    seed = int(time.time())
    print(f"Random seed: {seed}")
    random.seed(seed)
    
    # 10,000 digit numbers
    num1_10k = generate_random_number(10000)
    num2_10k = generate_random_number(10000)
    run_test(num1_10k, num2_10k, "10,000 digits 1", timeout=600)
    
    # 10,000 digit numbers (alternate, non-repetitive)
    num1_10k_alt = generate_random_number(10000)
    num2_10k_alt = generate_random_number(10000)
    run_test(num1_10k_alt, num2_10k_alt, "10,000 digits 2", timeout=600)
    
    # 50,000 digit numbers
    num1_50k = generate_random_number(50000)
    num2_50k = generate_random_number(50000)
    run_test(num1_50k, num2_50k, "50,000 digits", timeout=1200)
    
    # 1,000,000 digit numbers
    num1_1m = generate_random_number(1000000)
    num2_1m = generate_random_number(1000000)
    run_test(num1_1m, num2_1m, "1,000,000 digits", timeout=3600)


def run_hell_tests():
    """Run hell tests for 8-point tier"""
    print("Running hell tests for 8-point tier...")
    
    # Set random seed for reproducibility
    seed = int(time.time())
    print(f"Random seed: {seed}")
    random.seed(seed)
    
    for _ in range(10):
        # Generate two random numbers with 1,000,000 digits each
        num1 = generate_random_number(1000000)
        num2 = generate_random_number(1000000)
        run_test(num1, num2, "Hell test - 1,000,000 digits", timeout=3600)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--extreme":
        run_extreme_tests()
    elif len(sys.argv) > 1 and sys.argv[1] == "--hell":
        run_hell_tests()
    else:
        main()