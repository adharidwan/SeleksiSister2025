#include <stdio.h>

// Constants untuk NTT
#define MAX_SIZE 4194304  // 2^22
#define MOD 2013265921    // Prime: 15*2^27 + 1
#define ROOT 440564289    // Primitive root modulo MOD

unsigned long long a[MAX_SIZE];
unsigned long long b[MAX_SIZE];
unsigned long long c[MAX_SIZE];
unsigned int digits_a[3500000];
unsigned int digits_b[3500000];
unsigned int result[7000000];
char input_buffer[3500001];

#define IS_EQ(a, b) (!(a ^ b))
unsigned long long bit_sub(unsigned long long x, unsigned long long y) {
    bit_sub_loop:
    if (IS_EQ(y, 0)) goto bit_sub_done;
    
    unsigned long long borrow = (~x) & y;
    x = x ^ y;
    y = borrow << 1;
    goto bit_sub_loop;
    
    bit_sub_done:
    return x;
}
#define LT(a, b) ((bit_sub(a, b) >> 63) & 1)
#define GT(a, b) LT(b, a)
#define LE(a, b) (IS_EQ(a, b) | LT(a, b))
#define GE(a, b) (IS_EQ(a, b) | GT(a, b))

unsigned long long bit_add(unsigned long long x, unsigned long long y) {
    bit_add_loop:
    if (IS_EQ(y, 0)) goto bit_add_done;
    
    unsigned long long carry = x & y;
    x = x ^ y;
    y = carry << 1;
    goto bit_add_loop;
    
    bit_add_done:
    return x;
}

// Multiply by 10 using bitwise
unsigned long long mul_10(unsigned long long n) {
    unsigned long long t1 = n << 3;  // n * 8
    unsigned long long t2 = n << 1;  // n * 2
    return bit_add(t1, t2);          // n * 10
}

// Division by 10 using bitwise
unsigned long long div10(unsigned long long n) {
    if (LT(n, 10)) return 0;
    
    unsigned long long q = 0;
    unsigned long long r = 0;
    int i = 63;
    
    div_loop:
    if (LT(i, 0)) goto div_done;
    
    unsigned long long bit = (n >> i) & 1;
    r = (r << 1) | bit;
    
    if (GE(r, 10)) {
        r = bit_sub(r, 10);
        q = (q << 1) | 1;
        goto div_next;
    }
    q = q << 1;
    
    div_next:
    i = bit_sub(i, 1);
    goto div_loop;
    
    div_done:
    return q;
}

// Modular addition
unsigned long long add_mod(unsigned long long x, unsigned long long y, unsigned long long mod) {
    unsigned long long sum = bit_add(x, y);
    if (GE(sum, mod)) return bit_sub(sum, mod);
    return sum;
}

// Modular subtraction
unsigned long long sub_mod(unsigned long long x, unsigned long long y, unsigned long long mod) {
    unsigned long long temp = bit_sub(mod, y);
    unsigned long long res = bit_add(x, temp);
    if (GE(res, mod)) return bit_sub(res, mod);
    return res;
}

// Modular multiplication
unsigned long long mul_mod(unsigned long long x, unsigned long long y, unsigned long long mod) {
    unsigned long long res = 0;
    
    mul_mod_loop:
    if (IS_EQ(y, 0)) goto mul_mod_done;
    
    if (y & 1) {
        res = add_mod(res, x, mod);
    }
    
    x = add_mod(x, x, mod);
    y = y >> 1;
    goto mul_mod_loop;
    
    mul_mod_done:
    return res;
}

// Bitwise modulo operation
unsigned long long mod_reduce(unsigned long long dividend, unsigned long long divisor) {
    if (LT(dividend, divisor)) return dividend;
    
    int shift = 0;
    unsigned long long temp = divisor;
    loop_start:
    if (LE(temp, dividend)) {
        temp = temp << 1;
        shift = bit_add(shift, 1);
        goto loop_start;
    }
    shift = bit_sub(shift, 1);
    temp = temp >> 1;
    
    mod_loop:
    if (IS_EQ(shift, 0) && IS_EQ(temp, divisor)) {
        if (GE(dividend, divisor)) {
            dividend = bit_sub(dividend, divisor);
        }
        goto mod_done;
    }
    
    if (GE(dividend, temp)) {
        dividend = bit_sub(dividend, temp);
    }
    
    temp = temp >> 1;
    if (GT(shift, 0)) {
        shift = bit_sub(shift, 1);
    }
    goto mod_loop;
    
    mod_done:
    return dividend;
}

// Modular exponentiation
unsigned long long power_mod(unsigned long long base, unsigned long long exp, unsigned long long mod) {
    unsigned long long result = 1;
    base = mod_reduce(base, mod); 
    
    power_loop:
    if (IS_EQ(exp, 0)) goto power_done;
    
    if (exp & 1) {
        result = mul_mod(result, base, mod);
    }
    
    base = mul_mod(base, base, mod);
    exp = exp >> 1;
    goto power_loop;
    
    power_done:
    return result;
}

unsigned int bit_reverse(unsigned int num, unsigned int bits) {
    unsigned int result = 0;
    unsigned int i = 0;
    
    bit_rev_loop:
    if (GE(i, bits)) goto bit_rev_done;
    
    if (num & (1u << i)) {
        result = result | (1u << (bit_sub(bit_sub(bits, 1), i)));
    }
    i = bit_add(i, 1);
    goto bit_rev_loop;
    
    bit_rev_done:
    return result;
}

// NTT
void ntt(unsigned long long arr[], unsigned int n, unsigned int inverse) {
    unsigned int bits = 0;
    unsigned int temp_n = n;
    
    // Count bits
    count_bits:
    if (LE(temp_n, 1)) goto bits_done;
    bits = bit_add(bits, 1);
    temp_n = temp_n >> 1;
    goto count_bits;
    
    bits_done:
    
    // Bit-reversal permutation
    unsigned int i = 0;
    bit_rev_perm:
    if (GE(i, n)) goto bit_rev_perm_done;
    
    unsigned int j = bit_reverse(i, bits);
    if (LT(i, j)) {
        unsigned long long temp_val = arr[i];
        arr[i] = arr[j];
        arr[j] = temp_val;
    }
    i = bit_add(i, 1);
    goto bit_rev_perm;
    
    bit_rev_perm_done:
    
    // Main NTT computation
    unsigned int len = 2;
    
    ntt_outer:
    if (GT(len, n)) goto ntt_done;

    unsigned int k = 0;
    unsigned int temp = len;
    count_k:
    if (IS_EQ(temp, 1)) goto count_k_done;
    k = bit_add(k, 1);
    temp = temp >> 1;
    goto count_k;
    count_k_done:

    unsigned long long divisor = bit_sub(MOD, 1) >> k;

    unsigned long long wlen;
    if (inverse) {
        unsigned long long exponent = bit_sub(bit_sub(MOD, 1), divisor);
        wlen = power_mod(ROOT, exponent, MOD);
        goto wlen_computed;
    }
    wlen = power_mod(ROOT, divisor, MOD);
    
    wlen_computed:
    
    i = 0;
    ntt_groups:
    if (GE(i, n)) goto ntt_groups_done;
    
    unsigned long long w = 1;
    j = 0;
    
    ntt_inner:
    if (GE(j, (len >> 1))) goto ntt_inner_done;
    
    unsigned long long u = arr[bit_add(i, j)];
    unsigned long long v = mul_mod(arr[bit_add(bit_add(i, j), (len >> 1))], w, MOD);
    
    arr[bit_add(i, j)] = add_mod(u, v, MOD);
    arr[bit_add(bit_add(i, j), (len >> 1))] = sub_mod(u, v, MOD);
    
    w = mul_mod(w, wlen, MOD);
    j = bit_add(j, 1);
    goto ntt_inner;
    
    ntt_inner_done:
    i = bit_add(i, len);
    goto ntt_groups;
    
    ntt_groups_done:
    len = len << 1;
    goto ntt_outer;
    
    ntt_done:
    
    if (inverse) {
        unsigned long long n_inv = power_mod(n, bit_sub(MOD, 2), MOD);
        i = 0;
        normalize:
        if (GE(i, n)) goto normalize_done;
        arr[i] = mul_mod(arr[i], n_inv, MOD);
        i = bit_add(i, 1);
        goto normalize;
        normalize_done:
    }
}

// Convert string to digit array
unsigned int string_to_digits(char* str, unsigned int digits[]) {
    unsigned int len = 0;
    
    find_len:
    if (IS_EQ(str[len], '\0') | IS_EQ(str[len], '\n')) goto len_found;
    len = bit_add(len, 1);
    goto find_len;
    
    len_found:
    
    unsigned int i = 0;
    convert_loop:
    if (GE(i, len)) goto convert_done;
    digits[i] = bit_sub(str[bit_sub(bit_sub(len, 1), i)], '0');
    i = bit_add(i, 1);
    goto convert_loop;
    
    convert_done:
    return len;
}

// Print result from digit array
void digits_to_string(unsigned int digits[], unsigned int len) {
    unsigned int i = len;
    unsigned int started = 0;
    
    skip_zeros:
    if (IS_EQ(i, 0)) goto print_zero;
    i = bit_sub(i, 1);
    if (IS_EQ(digits[i], 0) & !started) goto skip_zeros;
    
    print_digits:
    printf("%u", digits[i]);
    started = 1;
    if (IS_EQ(i, 0)) goto print_done;
    i = bit_sub(i, 1);
    goto print_digits;
    
    print_zero:
    printf("0");
    
    print_done:
    printf("\n");
}

// Main multiplication function using NTT
void multiply_large(unsigned int a_digits[], unsigned int a_len, 
                   unsigned int b_digits[], unsigned int b_len) {
    unsigned int n = 1;
    unsigned int total_len = bit_add(a_len, b_len);
    
    // Find next power of 2
    find_n:
    if (GE(n, total_len)) goto n_found;
    n = n << 1;
    goto find_n;
    
    n_found:
    
    // Initialize arrays
    unsigned int i = 0;
    init_a:
    if (GE(i, n)) goto init_a_done;
    if (LT(i, a_len)) {
        a[i] = a_digits[i];
        goto next_a;
    }
    a[i] = 0;
    
    next_a:
    i = bit_add(i, 1);
    goto init_a;
    
    init_a_done:
    
    i = 0;
    init_b:
    if (GE(i, n)) goto init_b_done;
    if (LT(i, b_len)) {
        b[i] = b_digits[i];
        goto next_b;
    }
    b[i] = 0;
    
    next_b:
    i = bit_add(i, 1);
    goto init_b;
    
    init_b_done:
    
    // Apply NTT
    ntt(a, n, 0);
    ntt(b, n, 0);
    
    // Point-wise multiplication
    i = 0;
    multiply:
    if (GE(i, n)) goto multiply_done;
    c[i] = mul_mod(a[i], b[i], MOD);
    i = bit_add(i, 1);
    goto multiply;
    
    multiply_done:
    
    // Inverse NTT
    ntt(c, n, 1);
    
    // Handle carry propagation
    unsigned long long carry = 0;
    i = 0;
    
    carry_loop:
    if (GE(i, n)) goto carry_done;
    unsigned long long sum_val = bit_add(c[i], carry);
    unsigned long long carry_new = div10(sum_val);
    unsigned long long digit_val = bit_sub(sum_val, mul_10(carry_new));
    result[i] = digit_val;
    carry = carry_new;
    i = bit_add(i, 1);
    goto carry_loop;
    
    carry_done:
    
    // Handle remaining carry
    while_carry:
    if (IS_EQ(carry, 0)) goto carry_final_done;
    unsigned long long carry_temp = div10(carry);
    result[i] = bit_sub(carry, mul_10(carry_temp));
    carry = carry_temp;
    i = bit_add(i, 1);
    goto while_carry;
    
    carry_final_done:
    digits_to_string(result, i);
}

int main() {
    scanf("%s", input_buffer);
    unsigned int len_a = string_to_digits(input_buffer, digits_a);
    
    scanf("%s", input_buffer);
    unsigned int len_b = string_to_digits(input_buffer, digits_b);
    
    multiply_large(digits_a, len_a, digits_b, len_b);
    
    return 0;
}
