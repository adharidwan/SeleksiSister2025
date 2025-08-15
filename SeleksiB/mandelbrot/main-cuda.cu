#include <SFML/Graphics.hpp>
#include <iostream>
#include <complex>
#include <vector>
#include <chrono>
#include <thread>
#include <cmath>
#include <sstream>
#include <future>
#include <atomic>
#include <mutex>
#include <iomanip>

#include <cuda_runtime.h>
#include <device_launch_parameters.h>

class Button {
private:
    sf::RectangleShape shape;
    sf::Text text;
    sf::Font* font;
    bool is_pressed;
    
public:
    Button(float x, float y, float width, float height, const std::string& label, sf::Font& f) {
        font = &f;
        shape.setPosition(x, y);
        shape.setSize(sf::Vector2f(width, height));
        shape.setFillColor(sf::Color(70, 70, 70));
        shape.setOutlineColor(sf::Color(150, 150, 150));
        shape.setOutlineThickness(2);
        
        text.setFont(f);
        text.setString(label);
        text.setCharacterSize(14);
        text.setFillColor(sf::Color::White);
        
        sf::FloatRect textBounds = text.getLocalBounds();
        text.setPosition(
            x + (width - textBounds.width) / 2,
            y + (height - textBounds.height) / 2 - 2
        );
        
        is_pressed = false;
    }
    
    bool isClicked(sf::Vector2i mousePos) {
        return shape.getGlobalBounds().contains(static_cast<float>(mousePos.x), static_cast<float>(mousePos.y));
    }
    
    void setPressed(bool pressed) {
        is_pressed = pressed;
        if (pressed) {
            shape.setFillColor(sf::Color(100, 100, 100));
        } else {
            shape.setFillColor(sf::Color(70, 70, 70));
        }
    }
    
    void draw(sf::RenderWindow& window) {
        window.draw(shape);
        window.draw(text);
    }
    
    void updateText(const std::string& newText) {
        text.setString(newText);
        sf::FloatRect textBounds = text.getLocalBounds();
        sf::Vector2f pos = shape.getPosition();
        sf::Vector2f size = shape.getSize();
        text.setPosition(
            pos.x + (size.x - textBounds.width) / 2,
            pos.y + (size.y - textBounds.height) / 2 - 2
        );
    }
};

__device__ int cuda_mandelbrotIteration(double real, double imag, int max_iterations) {
    double z_real = 0.0;
    double z_imag = 0.0;
    int n = 0;
    
    while (z_real * z_real + z_imag * z_imag <= 4.0 && n < max_iterations) {
        double temp = z_real * z_real - z_imag * z_imag + real;
        z_imag = 2.0 * z_real * z_imag + imag;
        z_real = temp;
        n++;
    }
    
    return n;
}

__device__ int cuda_juliaIteration(double z_real, double z_imag, double c_real, double c_imag, int max_iterations) {
    int n = 0;
    
    while (z_real * z_real + z_imag * z_imag <= 4.0 && n < max_iterations) {
        double temp = z_real * z_real - z_imag * z_imag + c_real;
        z_imag = 2.0 * z_real * z_imag + c_imag;
        z_real = temp;
        n++;
    }
    
    return n;
}

__device__ void cuda_getColor(int iterations, int max_iterations, unsigned char* r, unsigned char* g, unsigned char* b) {
    if (iterations == max_iterations) {
        *r = *g = *b = 0;
        return;
    }
    
    double t = (double)iterations / max_iterations;
    
    *r = (unsigned char)(255 * (0.5 + 0.5 * cos(3.0 + t * 6.28)));
    *g = (unsigned char)(255 * (0.5 + 0.5 * cos(2.0 + t * 6.28)));
    *b = (unsigned char)(255 * (0.5 + 0.5 * cos(1.0 + t * 6.28)));
}

__global__ void cuda_generateFractal(unsigned char* pixels, int width, int height, 
                                    double min_real, double max_real, double min_imag, double max_imag,
                                    int max_iterations, bool julia_mode, double julia_c_real, double julia_c_imag) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    
    if (x >= width || y >= height) return;
    
    double real = min_real + (max_real - min_real) * x / (width - 1);
    double imag = min_imag + (max_imag - min_imag) * y / (height - 1);
    
    int iterations;
    if (julia_mode) {
        iterations = cuda_juliaIteration(real, imag, julia_c_real, julia_c_imag, max_iterations);
    } else {
        iterations = cuda_mandelbrotIteration(real, imag, max_iterations);
    }
    
    unsigned char r, g, b;
    cuda_getColor(iterations, max_iterations, &r, &g, &b);
    
    int index = (y * width + x) * 4;
    pixels[index] = r;         
    pixels[index + 1] = g;     
    pixels[index + 2] = b;     
    pixels[index + 3] = 255;   
}

class MandelbrotViewer {
private:
    int fractal_width, fractal_height, window_width, window_height;
    int max_iterations;
    double min_real, max_real, min_imag, max_imag;
    sf::RenderWindow window;
    sf::Image image;
    sf::Texture texture;
    sf::Sprite sprite;
    std::vector<sf::Uint8> pixels;
    sf::Font font;
    
    bool julia_mode;
    std::complex<double> julia_c;
    
    bool left_dragging;
    sf::Vector2i drag_start;
    sf::Vector2i current_mouse_pos;
    
    std::vector<Button> buttons;
    sf::Text info_text;
    sf::Text cursor_text;
    
    sf::Clock julia_update_clock;
    const float julia_update_interval = 0.1f;
    
    std::atomic<bool> is_generating;
    std::mutex pixel_mutex;
    int num_threads;
    
    unsigned char* d_pixels;
    bool cuda_available;
    bool use_cuda;
    
    enum ComputeMode { CPU_SERIAL, CPU_PARALLEL, GPU_CUDA };
    std::vector<double> benchmark_times;

public:
    MandelbrotViewer(int fw, int fh) : fractal_width(fw), fractal_height(fh), max_iterations(100),
                                      julia_mode(false), left_dragging(false), is_generating(false),
                                      d_pixels(nullptr), cuda_available(false), use_cuda(false) {
        initCuda();
        
        num_threads = std::max(1u, std::thread::hardware_concurrency());
        
        int gui_width = 250;
        window_width = fractal_width + gui_width;
        window_height = fractal_height;
        
        min_real = -2.5;
        max_real = 1.0;
        min_imag = -1.25;
        max_imag = 1.25;
        
        julia_c = std::complex<double>(-0.7, 0.27015);
        
        window.create(sf::VideoMode(window_width, window_height), "Interactive Mandelbrot/Julia Set with CUDA");
        window.setFramerateLimit(60);
        
        if (!font.loadFromFile("arial.ttf")) {
            if (!font.loadFromFile("C:/Windows/Fonts/arial.ttf") && 
                !font.loadFromFile("/System/Library/Fonts/Arial.ttf") &&
                !font.loadFromFile("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")) {
            }
        }
        
        image.create(fractal_width, fractal_height);
        texture.create(fractal_width, fractal_height);
        pixels.resize(fractal_width * fractal_height * 4);
        
        setupGUI(gui_width);
        generateFractal();
        updateTexture();
    }
    
    ~MandelbrotViewer() {
        if (d_pixels) {
            cudaFree(d_pixels);
        }
    }
    
    void initCuda() {
        int deviceCount = 0;
        cudaError_t error = cudaGetDeviceCount(&deviceCount);
        
        if (error != cudaSuccess || deviceCount == 0) {
            cuda_available = false;
            return;
        }
        
        cudaDeviceProp prop;
        cudaGetDeviceProperties(&prop, 0);
        
        size_t pixel_size = fractal_width * fractal_height * 4 * sizeof(unsigned char);
        error = cudaMalloc(&d_pixels, pixel_size);
        
        if (error != cudaSuccess) {
            cuda_available = false;
            return;
        }
        
        cuda_available = true;
        use_cuda = true;
    }
    
    void setupGUI(int gui_width) {
        float button_width = gui_width - 20;
        float button_height = 30;
        float start_x = fractal_width + 10;
        float start_y = 20;
        float spacing = button_height + 10;
        
        buttons.clear();
        
        buttons.emplace_back(start_x, start_y, button_width, button_height, 
                           julia_mode ? "Switch to Mandelbrot" : "Switch to Julia", font);
        
        buttons.emplace_back(start_x, start_y + spacing, button_width, button_height, 
                           "CPU Serial", font);
        buttons.emplace_back(start_x, start_y + 2*spacing, button_width, button_height, 
                           "CPU Parallel", font);
        if (cuda_available) {
            buttons.emplace_back(start_x, start_y + 3*spacing, button_width, button_height, 
                               "GPU CUDA (Active)", font);
        }
        
        int offset = cuda_available ? 1 : 0;
        buttons.emplace_back(start_x, start_y + (3+offset)*spacing, button_width, button_height, 
                           "Zoom In (Center)", font);
        buttons.emplace_back(start_x, start_y + (4+offset)*spacing, button_width, button_height, 
                           "Zoom Out (Center)", font);
        
        buttons.emplace_back(start_x, start_y + (5+offset)*spacing, button_width, button_height, 
                           "Reset View", font);
        
        buttons.emplace_back(start_x, start_y + (6+offset)*spacing, button_width, button_height, 
                           "More Iterations (+50)", font);
        buttons.emplace_back(start_x, start_y + (7+offset)*spacing, button_width, button_height, 
                           "Less Iterations (-50)", font);
        
        buttons.emplace_back(start_x, start_y + (8+offset)*spacing, button_width, button_height, 
                           "Run Benchmark", font);
        
        buttons.emplace_back(start_x, start_y + (9+offset)*spacing, button_width, button_height, 
                           "Julia: Classic", font);
        buttons.emplace_back(start_x, start_y + (10+offset)*spacing, button_width, button_height, 
                           "Julia: Dragon", font);
        buttons.emplace_back(start_x, start_y + (11+offset)*spacing, button_width, button_height, 
                           "Julia: Spiral", font);
        
        info_text.setFont(font);
        info_text.setCharacterSize(12);
        info_text.setFillColor(sf::Color::White);
        info_text.setPosition(start_x, start_y + (13+offset)*spacing);
        
        cursor_text.setFont(font);
        cursor_text.setCharacterSize(11);
        cursor_text.setFillColor(sf::Color(200, 200, 200));
        cursor_text.setPosition(start_x, window_height - 60);
        
        updateInfoText();
    }
    
    void updateInfoText() {
        std::stringstream ss;
        ss << "Mode: " << (julia_mode ? "Julia" : "Mandelbrot") << "\n";
        ss << "Compute: ";
        if (use_cuda && cuda_available) {
            ss << "GPU CUDA";
        } else {
            ss << "CPU (" << num_threads << " threads)";
        }
        ss << "\n";
        ss << "Iterations: " << max_iterations << "\n";
        ss << "Zoom: " << std::fixed << std::setprecision(2) << (3.5 / (max_real - min_real)) << "x\n";
        if (julia_mode) {
            ss << "Julia C: " << std::fixed << std::setprecision(3) 
               << julia_c.real() << " + " << julia_c.imag() << "i\n";
        }
        
        if (!benchmark_times.empty() && benchmark_times.size() >= 2) {
            ss << "\nBenchmark Results:\n";
            ss << "CPU Serial: " << std::fixed << std::setprecision(1) << benchmark_times[0] << "ms\n";
            ss << "CPU Parallel: " << std::fixed << std::setprecision(1) << benchmark_times[1] << "ms\n";
            if (cuda_available && benchmark_times.size() >= 3) {
                ss << "GPU CUDA: " << std::fixed << std::setprecision(1) << benchmark_times[2] << "ms\n";
                ss << "Speedup vs Serial: " << std::fixed << std::setprecision(1) 
                   << benchmark_times[0] / benchmark_times[2] << "x\n";
                ss << "Speedup vs Parallel: " << std::fixed << std::setprecision(1) 
                   << benchmark_times[1] / benchmark_times[2] << "x\n";
            }
        }
        
        ss << "\nControls:\n";
        ss << "- Left click + drag to pan\n";
        ss << "- Mouse wheel to zoom\n  at cursor position\n";
        if (julia_mode) {
            ss << "- Move mouse over\n  fractal to change C";
        }
        
        info_text.setString(ss.str());
    }
    
    void updateCursorText() {
        if (current_mouse_pos.x < fractal_width && current_mouse_pos.y >= 0 && 
            current_mouse_pos.y < fractal_height) {
            double real = min_real + (max_real - min_real) * current_mouse_pos.x / (fractal_width - 1);
            double imag = min_imag + (max_imag - min_imag) * current_mouse_pos.y / (fractal_height - 1);
            
            std::stringstream ss;
            ss << "Cursor Position:\n";
            ss << "Screen: (" << current_mouse_pos.x << ", " << current_mouse_pos.y << ")\n";
            ss << "Complex: " << std::fixed << std::setprecision(6) 
               << real << " + " << imag << "i";
            
            cursor_text.setString(ss.str());
        } else {
            cursor_text.setString("Cursor Position:\n(Outside fractal area)");
        }
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
    
    int juliaIteration(std::complex<double> z, std::complex<double> c) {
        int n = 0;
        
        while (std::abs(z) <= 2.0 && n < max_iterations) {
            z = z * z + c;
            n++;
        }
        
        return n;
    }
    
    sf::Color getColor(int iterations) {
        if (iterations == max_iterations) {
            return sf::Color::Black;
        }
        
        double t = (double)iterations / max_iterations;
        
        uint8_t r = static_cast<uint8_t>(255 * (0.5 + 0.5 * std::cos(3.0 + t * 6.28)));
        uint8_t g = static_cast<uint8_t>(255 * (0.5 + 0.5 * std::cos(2.0 + t * 6.28)));
        uint8_t b = static_cast<uint8_t>(255 * (0.5 + 0.5 * std::cos(1.0 + t * 6.28)));
        
        return sf::Color(r, g, b);
    }
    
    void generateFractalSerial() {
        for (int y = 0; y < fractal_height; y++) {
            for (int x = 0; x < fractal_width; x++) {
                double real = min_real + (max_real - min_real) * x / (fractal_width - 1);
                double imag = min_imag + (max_imag - min_imag) * y / (fractal_height - 1);
                
                int iterations;
                if (julia_mode) {
                    std::complex<double> z(real, imag);
                    iterations = juliaIteration(z, julia_c);
                } else {
                    std::complex<double> c(real, imag);
                    iterations = mandelbrotIteration(c);
                }
                
                sf::Color color = getColor(iterations);
                
                int index = (y * fractal_width + x) * 4;
                pixels[index] = color.r;     
                pixels[index + 1] = color.g; 
                pixels[index + 2] = color.b; 
                pixels[index + 3] = 255;     
            }
        }
    }
    
    void generateFractalChunk(int start_y, int end_y, std::vector<sf::Uint8>& local_pixels) {
        for (int y = start_y; y < end_y; y++) {
            for (int x = 0; x < fractal_width; x++) {
                double real = min_real + (max_real - min_real) * x / (fractal_width - 1);
                double imag = min_imag + (max_imag - min_imag) * y / (fractal_height - 1);
                
                int iterations;
                if (julia_mode) {
                    std::complex<double> z(real, imag);
                    iterations = juliaIteration(z, julia_c);
                } else {
                    std::complex<double> c(real, imag);
                    iterations = mandelbrotIteration(c);
                }
                
                sf::Color color = getColor(iterations);
                
                int index = ((y - start_y) * fractal_width + x) * 4;
                local_pixels[index] = color.r;     
                local_pixels[index + 1] = color.g; 
                local_pixels[index + 2] = color.b; 
                local_pixels[index + 3] = 255;     
            }
        }
    }
    
    void generateFractalParallel() {
        int rows_per_thread = fractal_height / num_threads;
        int remaining_rows = fractal_height % num_threads;
        
        std::vector<std::future<void>> futures;
        std::vector<std::vector<sf::Uint8>> thread_pixels(num_threads);
        
        int current_y = 0;
        for (int t = 0; t < num_threads; t++) {
            int start_y = current_y;
            int rows_to_process = rows_per_thread + (t < remaining_rows ? 1 : 0);
            int end_y = start_y + rows_to_process;
            current_y = end_y;
            
            thread_pixels[t].resize(rows_to_process * fractal_width * 4);
            
            futures.push_back(std::async(std::launch::async, 
                [this, start_y, end_y, &thread_pixels, t]() {
                    generateFractalChunk(start_y, end_y, thread_pixels[t]);
                }));
        }
        
        for (auto& future : futures) {
            future.wait();
        }
        
        current_y = 0;
        for (int t = 0; t < num_threads; t++) {
            int start_y = current_y;
            int rows_to_process = rows_per_thread + (t < remaining_rows ? 1 : 0);
            current_y += rows_to_process;
            
            for (int local_y = 0; local_y < rows_to_process; local_y++) {
                int global_y = start_y + local_y;
                for (int x = 0; x < fractal_width; x++) {
                    int local_index = (local_y * fractal_width + x) * 4;
                    int global_index = (global_y * fractal_width + x) * 4;
                    
                    pixels[global_index] = thread_pixels[t][local_index];         
                    pixels[global_index + 1] = thread_pixels[t][local_index + 1]; 
                    pixels[global_index + 2] = thread_pixels[t][local_index + 2]; 
                    pixels[global_index + 3] = thread_pixels[t][local_index + 3]; 
                }
            }
        }
    }
    
    void generateFractalCuda() {
        if (!cuda_available || !d_pixels) return;
        
        dim3 blockSize(16, 16);
        dim3 gridSize((fractal_width + blockSize.x - 1) / blockSize.x,
                      (fractal_height + blockSize.y - 1) / blockSize.y);
        
        cuda_generateFractal<<<gridSize, blockSize>>>(
            d_pixels, fractal_width, fractal_height,
            min_real, max_real, min_imag, max_imag,
            max_iterations, julia_mode, julia_c.real(), julia_c.imag()
        );
        
        cudaError_t error = cudaGetLastError();
        if (error != cudaSuccess) {
            return;
        }
        
        cudaDeviceSynchronize();
        
        size_t pixel_size = fractal_width * fractal_height * 4 * sizeof(unsigned char);
        cudaMemcpy(pixels.data(), d_pixels, pixel_size, cudaMemcpyDeviceToHost);
    }
    
    void generateFractal() {
        if (is_generating.exchange(true)) {
            return;
        }
        
        auto start = std::chrono::high_resolution_clock::now();
        
        if (use_cuda && cuda_available) {
            generateFractalCuda();
        } else {
            generateFractalParallel();
        }
        
        auto end = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
        
        std::string compute_method = use_cuda && cuda_available ? "CUDA GPU" : ("CPU (" + std::to_string(num_threads) + " threads)");
        
        is_generating = false;
    }
    
    void runBenchmark() {
        if (is_generating.load()) return;
        
        benchmark_times.clear();
        
        bool original_use_cuda = use_cuda;
        
        use_cuda = false;
        auto start = std::chrono::high_resolution_clock::now();
        generateFractalSerial();
        auto end = std::chrono::high_resolution_clock::now();
        double serial_time = std::chrono::duration<double, std::milli>(end - start).count();
        benchmark_times.push_back(serial_time);
        
        start = std::chrono::high_resolution_clock::now();
        generateFractalParallel();
        end = std::chrono::high_resolution_clock::now();
        double parallel_time = std::chrono::duration<double, std::milli>(end - start).count();
        benchmark_times.push_back(parallel_time);
        
        if (cuda_available) {
            use_cuda = true;
            start = std::chrono::high_resolution_clock::now();
            generateFractalCuda();
            end = std::chrono::high_resolution_clock::now();
            double cuda_time = std::chrono::duration<double, std::milli>(end - start).count();
            benchmark_times.push_back(cuda_time);
        }
        
        use_cuda = original_use_cuda;
        
        updateTexture();
        updateInfoText();
    }
    
    void updateTexture() {
        texture.update(pixels.data());
        sprite.setTexture(texture);
    }
    
    void zoom(int mouse_x, int mouse_y, double factor) {
        double center_real = min_real + (max_real - min_real) * mouse_x / (fractal_width - 1);
        double center_imag = min_imag + (max_imag - min_imag) * mouse_y / (fractal_height - 1);
        
        double real_range = (max_real - min_real) * factor;
        double imag_range = (max_imag - min_imag) * factor;
        
        min_real = center_real - real_range / 2.0;
        max_real = center_real + real_range / 2.0;
        min_imag = center_imag - imag_range / 2.0;
        max_imag = center_imag + imag_range / 2.0;
    }
    
    void zoomCenter(double factor) {
        double center_real = (min_real + max_real) / 2.0;
        double center_imag = (min_imag + max_imag) / 2.0;
        
        double real_range = (max_real - min_real) * factor;
        double imag_range = (max_imag - min_imag) * factor;
        
        min_real = center_real - real_range / 2.0;
        max_real = center_real + real_range / 2.0;
        min_imag = center_imag - imag_range / 2.0;
        max_imag = center_imag + imag_range / 2.0;
    }
    
    void pan(int dx, int dy) {
        double real_range = max_real - min_real;
        double imag_range = max_imag - min_imag;
        
        double real_delta = -dx * real_range / fractal_width;
        double imag_delta = -dy * imag_range / fractal_height;
        
        min_real += real_delta;
        max_real += real_delta;
        min_imag += imag_delta;
        max_imag += imag_delta;
    }
    
    void resetView() {
        if (julia_mode) {
            min_real = -2.0;
            max_real = 2.0;
            min_imag = -2.0;
            max_imag = 2.0;
        } else {
            min_real = -2.5;
            max_real = 1.0;
            min_imag = -1.25;
            max_imag = 1.25;
        }
    }
    
    void handleButtonClick(int button_index) {
        int offset = cuda_available ? 1 : 0;
        int adjusted_index = button_index - offset;

        switch (button_index) {
            case 0:
                julia_mode = !julia_mode;
                resetView();
                buttons[0].updateText(julia_mode ? "Switch to Mandelbrot" : "Switch to Julia");
                generateFractal();
                updateTexture();
                updateInfoText();
                break;

            case 1:
                use_cuda = false;
                buttons[1].updateText("CPU Serial (Active)");
                buttons[2].updateText("CPU Parallel");
                if (cuda_available) buttons[3].updateText("GPU CUDA");
                generateFractal();
                updateTexture();
                updateInfoText();
                break;

            case 2:
                use_cuda = false;
                buttons[1].updateText("CPU Serial");
                buttons[2].updateText("CPU Parallel (Active)");
                if (cuda_available) buttons[3].updateText("GPU CUDA");
                generateFractal();
                updateTexture();
                updateInfoText();
                break;

            case 3:
                if (cuda_available) {
                    use_cuda = true;
                    buttons[1].updateText("CPU Serial");
                    buttons[2].updateText("CPU Parallel");
                    buttons[3].updateText("GPU CUDA (Active)");
                    generateFractal();
                    updateTexture();
                    updateInfoText();
                }
                break;

            default:
                switch (adjusted_index) {
                    case 3:
                        zoomCenter(0.5);
                        generateFractal();
                        updateTexture();
                        updateInfoText();
                        break;

                    case 4:
                        zoomCenter(2.0);
                        generateFractal();
                        updateTexture();
                        updateInfoText();
                        break;

                    case 5:
                        resetView();
                        generateFractal();
                        updateTexture();
                        updateInfoText();
                        break;

                    case 6:
                        max_iterations += 50;
                        generateFractal();
                        updateTexture();
                        updateInfoText();
                        break;

                    case 7:
                        if (max_iterations > 50) {
                            max_iterations -= 50;
                            generateFractal();
                            updateTexture();
                            updateInfoText();
                        }
                        break;

                    case 8:
                        runBenchmark();
                        break;

                    case 9:
                        if (julia_mode) {
                            julia_c = std::complex<double>(-0.7, 0.27015);
                            generateFractal();
                            updateTexture();
                            updateInfoText();
                        }
                        break;

                    case 10:
                        if (julia_mode) {
                            julia_c = std::complex<double>(-0.8, 0.156);
                            generateFractal();
                            updateTexture();
                            updateInfoText();
                        }
                        break;

                    case 11:
                        if (julia_mode) {
                            julia_c = std::complex<double>(-0.4, 0.6);
                            generateFractal();
                            updateTexture();
                            updateInfoText();
                        }
                        break;
                }
                break;
        }
    }
    
    void handleEvents() {
        sf::Event event;
        while (window.pollEvent(event)) {
            switch (event.type) {
                case sf::Event::Closed:
                    window.close();
                    break;
                    
                case sf::Event::MouseButtonPressed:
                    if (event.mouseButton.button == sf::Mouse::Left) {
                        sf::Vector2i mousePos(event.mouseButton.x, event.mouseButton.y);
                        
                        bool button_clicked = false;
                        for (size_t i = 0; i < buttons.size(); i++) {
                            if (buttons[i].isClicked(mousePos)) {
                                int offset = cuda_available ? 1 : 0;
                                if (i >= 9+offset && i <= 11+offset && !julia_mode) continue;
                                
                                buttons[i].setPressed(true);
                                handleButtonClick(i);
                                button_clicked = true;
                                break;
                            }
                        }
                        
                        if (!button_clicked && event.mouseButton.x < fractal_width) {
                            left_dragging = true;
                            drag_start = mousePos;
                        }
                    }
                    break;
                    
                case sf::Event::MouseButtonReleased:
                    if (event.mouseButton.button == sf::Mouse::Left) {
                        for (auto& button : buttons) {
                            button.setPressed(false);
                        }
                        
                        left_dragging = false;
                    }
                    break;
                    
                case sf::Event::MouseMoved:
                    current_mouse_pos = sf::Vector2i(event.mouseMove.x, event.mouseMove.y);
                    updateCursorText();
                    
                    if (julia_mode && event.mouseMove.x < fractal_width && 
                        !left_dragging &&
                        julia_update_clock.getElapsedTime().asSeconds() > julia_update_interval) {
                        double real = (double)event.mouseMove.x / fractal_width * 4.0 - 2.0;
                        double imag = (double)event.mouseMove.y / fractal_height * 4.0 - 2.0;
                        julia_c = std::complex<double>(real, imag);
                        
                        generateFractal();
                        updateTexture();
                        updateInfoText();
                        julia_update_clock.restart();
                    } else if (left_dragging && event.mouseMove.x < fractal_width) {
                        sf::Vector2i current_pos(event.mouseMove.x, event.mouseMove.y);
                        sf::Vector2i delta = current_pos - drag_start;
                        
                        pan(delta.x, delta.y);
                        drag_start = current_pos;
                        
                        generateFractal();
                        updateTexture();
                        updateInfoText();
                    }
                    break;
                    
                case sf::Event::MouseWheelScrolled:
                    if (event.mouseWheelScroll.x < fractal_width) {
                        if (event.mouseWheelScroll.delta > 0) {
                            zoom(event.mouseWheelScroll.x, event.mouseWheelScroll.y, 0.8);
                        } else {
                            zoom(event.mouseWheelScroll.x, event.mouseWheelScroll.y, 1.25);
                        }
                        generateFractal();
                        updateTexture();
                        updateInfoText();
                    }
                    break;
            }
        }
    }
    
    void run() {
        while (window.isOpen()) {
            handleEvents();
            
            window.clear(sf::Color(40, 40, 40));
            
            window.draw(sprite);
            
            sf::RectangleShape gui_panel(sf::Vector2f(250, window_height));
            gui_panel.setPosition(fractal_width, 0);
            gui_panel.setFillColor(sf::Color(30, 30, 30));
            window.draw(gui_panel);
            
            int offset = cuda_available ? 1 : 0;
            for (size_t i = 0; i < buttons.size(); i++) {
                if (i >= 9+offset && i <= 11+offset && !julia_mode) continue;
                buttons[i].draw(window);
            }
            
            window.draw(info_text);
            
            window.draw(cursor_text);
            
            window.display();
        }
    }
};

int main() {
    int width = 800, height = 600;
    
    std::string input;
    std::getline(std::cin, input);
    
    if (!input.empty()) {
        std::stringstream ss(input);
        ss >> width >> height;
    }
    
    try {
        MandelbrotViewer viewer(width, height);
        viewer.run();
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}