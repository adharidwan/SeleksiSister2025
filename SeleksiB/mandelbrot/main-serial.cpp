#include <iostream>
#include <complex>
#include <vector>
#include <chrono>
#include <fstream>
#include <cmath>

// Simple BMP header structures
#pragma pack(push, 1)
struct BMPFileHeader {
    uint16_t file_type{0x4D42};
    uint32_t file_size{0};
    uint16_t reserved1{0};
    uint16_t reserved2{0};
    uint32_t offset_data{0};
};

struct BMPInfoHeader {
    uint32_t size{0};
    int32_t width{0};
    int32_t height{0};
    uint16_t planes{1};
    uint16_t bit_count{0};
    uint32_t compression{0};
    uint32_t size_image{0};
    int32_t x_pixels_per_meter{0};
    int32_t y_pixels_per_meter{0};
    uint32_t colors_used{0};
    uint32_t colors_important{0};
};
#pragma pack(pop)

class MandelbrotGenerator {
private:
    int width, height;
    int max_iterations;
    double min_real, max_real, min_imag, max_imag;
    std::vector<std::vector<int>> iterations;

public:
    MandelbrotGenerator(int w, int h, int max_iter = 1000) 
        : width(w), height(h), max_iterations(max_iter) {
        // Default Mandelbrot set bounds
        min_real = -2.5;
        max_real = 1.0;
        min_imag = -1.25;
        max_imag = 1.25;
        
        iterations.resize(height, std::vector<int>(width));
    }
    
    void setBounds(double min_r, double max_r, double min_i, double max_i) {
        min_real = min_r;
        max_real = max_r;
        min_imag = min_i;
        max_imag = max_i;
    }
    
    int mandelbrotIteration(std::complex<double> c) {
        std::complex<double> z = 0;
        int n = 0;
        
        while (std::abs(z) <= 2.0 && n < max_iterations) {
            z = z * z + c;
            n++;
        }
        
        return n;
    }
    
    void generateSerial() {
        auto start = std::chrono::high_resolution_clock::now();
        
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                // Map pixel coordinates to complex plane
                double real = min_real + (max_real - min_real) * x / (width - 1);
                double imag = min_imag + (max_imag - min_imag) * y / (height - 1);
                
                std::complex<double> c(real, imag);
                iterations[y][x] = mandelbrotIteration(c);
            }
        }
        
        auto end = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
        
        std::cout << "Serial execution time: " << duration.count() << " ms" << std::endl;
    }
    
    void saveBMP(const std::string& filename) {
        std::ofstream file(filename, std::ios::binary);
        if (!file) {
            std::cerr << "Error: Could not open file " << filename << std::endl;
            return;
        }
        
        // Calculate padding for 4-byte alignment
        int padding = (4 - (width * 3) % 4) % 4;
        int row_size = width * 3 + padding;
        
        BMPFileHeader file_header;
        file_header.file_size = sizeof(BMPFileHeader) + sizeof(BMPInfoHeader) + row_size * height;
        file_header.offset_data = sizeof(BMPFileHeader) + sizeof(BMPInfoHeader);
        
        BMPInfoHeader info_header;
        info_header.size = sizeof(BMPInfoHeader);
        info_header.width = width;
        info_header.height = height;
        info_header.bit_count = 24;
        info_header.size_image = row_size * height;
        
        file.write(reinterpret_cast<char*>(&file_header), sizeof(file_header));
        file.write(reinterpret_cast<char*>(&info_header), sizeof(info_header));
        
        // Color mapping
        std::vector<uint8_t> row(row_size, 0);
        
        for (int y = height - 1; y >= 0; y--) { // BMP is bottom-up
            for (int x = 0; x < width; x++) {
                int iter = iterations[y][x];
                uint8_t color;
                
                if (iter == max_iterations) {
                    color = 0; // Black for points in the set
                } else {
                    // Smooth coloring
                    color = static_cast<uint8_t>(255 * iter / max_iterations);
                }
                
                // BGR format
                row[x * 3] = color;     // Blue
                row[x * 3 + 1] = color; // Green
                row[x * 3 + 2] = color; // Red
            }
            file.write(reinterpret_cast<char*>(row.data()), row_size);
        }
        
        file.close();
        std::cout << "Image saved as " << filename << std::endl;
    }
    
    std::vector<std::vector<int>>& getIterations() {
        return iterations;
    }
};

int main() {
    std::cout << "=== Mandelbrot Set Generator (Serial) ===" << std::endl;
    
    int width, height;
    std::cout << "Enter image dimensions (width height): ";
    std::cin >> width >> height;
    
    MandelbrotGenerator generator(width, height);
    
    std::cout << "Generating Mandelbrot set..." << std::endl;
    generator.generateSerial();
    
    std::string filename = "mandelbrot_serial_" + std::to_string(width) + "x" + std::to_string(height) + ".bmp";
    generator.saveBMP(filename);
    
    return 0;
}