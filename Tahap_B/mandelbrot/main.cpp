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
        
        // Center text in button
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
    
    // Julia set parameters
    bool julia_mode;
    std::complex<double> julia_c;
    
    // UI state - separate tracking for left and right mouse buttons
    bool left_dragging;
    bool right_dragging;
    sf::Vector2i left_drag_start;
    sf::Vector2i right_drag_start;
    
    // GUI elements
    std::vector<Button> buttons;
    sf::Text info_text;
    
    // Performance optimization
    sf::Clock julia_update_clock;
    const float julia_update_interval = 0.1f; // Update Julia set every 100ms
    
    // Multithreading
    std::atomic<bool> is_generating;
    std::mutex pixel_mutex;
    int num_threads;

public:
    MandelbrotViewer(int fw, int fh) : fractal_width(fw), fractal_height(fh), max_iterations(100),
                                      julia_mode(false), left_dragging(false), right_dragging(false), is_generating(false) {
        // Detect number of CPU cores
        num_threads = std::max(1u, std::thread::hardware_concurrency());
        std::cout << "Using " << num_threads << " threads for fractal generation" << std::endl;
        // GUI panel width
        int gui_width = 200;
        window_width = fractal_width + gui_width;
        window_height = fractal_height;
        
        // Default Mandelbrot bounds
        min_real = -2.5;
        max_real = 1.0;
        min_imag = -1.25;
        max_imag = 1.25;
        
        julia_c = std::complex<double>(-0.7, 0.27015);
        
        window.create(sf::VideoMode(window_width, window_height), "Interactive Mandelbrot/Julia Set");
        window.setFramerateLimit(60);
        
        // Load font
        if (!font.loadFromFile("arial.ttf")) {
            // Try system font paths
            if (!font.loadFromFile("C:/Windows/Fonts/arial.ttf") && 
                !font.loadFromFile("/System/Library/Fonts/Arial.ttf") &&
                !font.loadFromFile("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")) {
                std::cout << "Warning: Could not load font. Using default font." << std::endl;
            }
        }
        
        image.create(fractal_width, fractal_height);
        texture.create(fractal_width, fractal_height);
        pixels.resize(fractal_width * fractal_height * 4); // RGBA
        
        setupGUI(gui_width);
        generateFractal();
        updateTexture();
    }
    
    void setupGUI(int gui_width) {
        float button_width = gui_width - 20;
        float button_height = 30;
        float start_x = fractal_width + 10;
        float start_y = 20;
        float spacing = button_height + 10;
        
        buttons.clear();
        
        // Toggle Mode button
        buttons.emplace_back(start_x, start_y, button_width, button_height, 
                           julia_mode ? "Switch to Mandelbrot" : "Switch to Julia", font);
        
        // Zoom buttons
        buttons.emplace_back(start_x, start_y + spacing, button_width, button_height, 
                           "Zoom In (Center)", font);
        buttons.emplace_back(start_x, start_y + 2*spacing, button_width, button_height, 
                           "Zoom Out (Center)", font);
        
        // Reset button
        buttons.emplace_back(start_x, start_y + 3*spacing, button_width, button_height, 
                           "Reset View", font);
        
        // Iteration buttons
        buttons.emplace_back(start_x, start_y + 4*spacing, button_width, button_height, 
                           "More Iterations (+50)", font);
        buttons.emplace_back(start_x, start_y + 5*spacing, button_width, button_height, 
                           "Less Iterations (-50)", font);
        
        // Julia constant buttons (only show in Julia mode)
        buttons.emplace_back(start_x, start_y + 6*spacing, button_width, button_height, 
                           "Julia: Classic", font);
        buttons.emplace_back(start_x, start_y + 7*spacing, button_width, button_height, 
                           "Julia: Dragon", font);
        buttons.emplace_back(start_x, start_y + 8*spacing, button_width, button_height, 
                           "Julia: Spiral", font);
        
        // Info text
        info_text.setFont(font);
        info_text.setCharacterSize(12);
        info_text.setFillColor(sf::Color::White);
        info_text.setPosition(start_x, start_y + 10*spacing);
        updateInfoText();
    }
    
    void updateInfoText() {
        std::stringstream ss;
        ss << "Mode: " << (julia_mode ? "Julia" : "Mandelbrot") << "\n";
        ss << "Iterations: " << max_iterations << "\n";
        ss << "Zoom: " << std::fixed << std::setprecision(2) << (3.5 / (max_real - min_real)) << "x\n";
        ss << "Threads: " << num_threads << "\n";
        if (julia_mode) {
            ss << "Julia C: " << std::fixed << std::setprecision(3) 
               << julia_c.real() << " + " << julia_c.imag() << "i\n";
        }
        ss << "\nControls:\n";
        ss << "- Left click fractal to zoom\n";
        ss << "- Right click + drag to pan\n";
        ss << "- Mouse wheel to zoom\n";
        if (julia_mode) {
            ss << "- Move mouse over\n  fractal to change C";
        }
        
        info_text.setString(ss.str());
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
        
        // Smooth coloring with multiple color schemes
        double t = (double)iterations / max_iterations;
        
        // Rainbow coloring
        uint8_t r = static_cast<uint8_t>(255 * (0.5 + 0.5 * std::cos(3.0 + t * 6.28)));
        uint8_t g = static_cast<uint8_t>(255 * (0.5 + 0.5 * std::cos(2.0 + t * 6.28)));
        uint8_t b = static_cast<uint8_t>(255 * (0.5 + 0.5 * std::cos(1.0 + t * 6.28)));
        
        return sf::Color(r, g, b);
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
                local_pixels[index] = color.r;     // Red
                local_pixels[index + 1] = color.g; // Green
                local_pixels[index + 2] = color.b; // Blue
                local_pixels[index + 3] = 255;     // Alpha
            }
        }
    }
    
    void generateFractal() {
        // Prevent multiple simultaneous generations
        if (is_generating.exchange(true)) {
            return;
        }
        
        auto start = std::chrono::high_resolution_clock::now();
        
        // Calculate work distribution for threads
        int rows_per_thread = fractal_height / num_threads;
        int remaining_rows = fractal_height % num_threads;
        
        // Create threads and local pixel buffers
        std::vector<std::future<void>> futures;
        std::vector<std::vector<sf::Uint8>> thread_pixels(num_threads);
        
        int current_y = 0;
        for (int t = 0; t < num_threads; t++) {
            int start_y = current_y;
            int rows_to_process = rows_per_thread + (t < remaining_rows ? 1 : 0);
            int end_y = start_y + rows_to_process;
            current_y = end_y;
            
            // Allocate pixel buffer for this thread
            thread_pixels[t].resize(rows_to_process * fractal_width * 4);
            
            // Launch thread
            futures.push_back(std::async(std::launch::async, 
                [this, start_y, end_y, &thread_pixels, t]() {
                    generateFractalChunk(start_y, end_y, thread_pixels[t]);
                }));
        }
        
        // Wait for all threads to complete
        for (auto& future : futures) {
            future.wait();
        }
        
        // Combine results from all threads into main pixel buffer
        current_y = 0;
        for (int t = 0; t < num_threads; t++) {
            int start_y = current_y;
            int rows_to_process = rows_per_thread + (t < remaining_rows ? 1 : 0);
            current_y += rows_to_process;
            
            // Copy thread's pixels to main buffer
            for (int local_y = 0; local_y < rows_to_process; local_y++) {
                int global_y = start_y + local_y;
                for (int x = 0; x < fractal_width; x++) {
                    int local_index = (local_y * fractal_width + x) * 4;
                    int global_index = (global_y * fractal_width + x) * 4;
                    
                    pixels[global_index] = thread_pixels[t][local_index];         // Red
                    pixels[global_index + 1] = thread_pixels[t][local_index + 1]; // Green
                    pixels[global_index + 2] = thread_pixels[t][local_index + 2]; // Blue
                    pixels[global_index + 3] = thread_pixels[t][local_index + 3]; // Alpha
                }
            }
        }
        
        auto end = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
        
        std::cout << (julia_mode ? "Julia" : "Mandelbrot") << " generation time: " 
                  << duration.count() << " ms (" << num_threads << " threads)" << std::endl;
        
        is_generating = false;
    }
    
    void updateTexture() {
        texture.update(pixels.data());
        sprite.setTexture(texture);
    }
    
    void zoom(int mouse_x, int mouse_y, double factor) {
        // Convert mouse coordinates to complex plane
        double center_real = min_real + (max_real - min_real) * mouse_x / (fractal_width - 1);
        double center_imag = min_imag + (max_imag - min_imag) * mouse_y / (fractal_height - 1);
        
        // Calculate new bounds centered on mouse position
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
        switch (button_index) {
            case 0: // Toggle Mode
                julia_mode = !julia_mode;
                resetView();
                buttons[0].updateText(julia_mode ? "Switch to Mandelbrot" : "Switch to Julia");
                generateFractal();
                updateTexture();
                updateInfoText();
                break;
                
            case 1: // Zoom In Center
                zoomCenter(0.5);
                generateFractal();
                updateTexture();
                updateInfoText();
                break;
                
            case 2: // Zoom Out Center
                zoomCenter(2.0);
                generateFractal();
                updateTexture();
                updateInfoText();
                break;
                
            case 3: // Reset View
                resetView();
                generateFractal();
                updateTexture();
                updateInfoText();
                break;
                
            case 4: // More Iterations
                max_iterations += 50;
                generateFractal();
                updateTexture();
                updateInfoText();
                break;
                
            case 5: // Less Iterations
                if (max_iterations > 50) {
                    max_iterations -= 50;
                    generateFractal();
                    updateTexture();
                    updateInfoText();
                }
                break;
                
            case 6: // Julia Classic
                if (julia_mode) {
                    julia_c = std::complex<double>(-0.7, 0.27015);
                    generateFractal();
                    updateTexture();
                    updateInfoText();
                }
                break;
                
            case 7: // Julia Dragon
                if (julia_mode) {
                    julia_c = std::complex<double>(-0.8, 0.156);
                    generateFractal();
                    updateTexture();
                    updateInfoText();
                }
                break;
                
            case 8: // Julia Spiral
                if (julia_mode) {
                    julia_c = std::complex<double>(-0.4, 0.6);
                    generateFractal();
                    updateTexture();
                    updateInfoText();
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
                        
                        // Check button clicks
                        bool button_clicked = false;
                        for (size_t i = 0; i < buttons.size(); i++) {
                            if (buttons[i].isClicked(mousePos)) {
                                // Only show Julia buttons in Julia mode
                                if (i >= 6 && i <= 8 && !julia_mode) continue;
                                
                                buttons[i].setPressed(true);
                                handleButtonClick(i);
                                button_clicked = true;
                                break;
                            }
                        }
                        
                        // If not clicking a button and clicking on fractal area
                        if (!button_clicked && event.mouseButton.x < fractal_width) {
                            left_dragging = true;
                            left_drag_start = mousePos;
                        }
                    }
                    else if (event.mouseButton.button == sf::Mouse::Right) {
                        // Right click for panning
                        if (event.mouseButton.x < fractal_width) {
                            right_dragging = true;
                            right_drag_start = sf::Vector2i(event.mouseButton.x, event.mouseButton.y);
                        }
                    }
                    break;
                    
                case sf::Event::MouseButtonReleased:
                    if (event.mouseButton.button == sf::Mouse::Left) {
                        // Reset all button states
                        for (auto& button : buttons) {
                            button.setPressed(false);
                        }
                        
                        if (left_dragging) {
                            left_dragging = false;
                            
                            sf::Vector2i drag_end(event.mouseButton.x, event.mouseButton.y);
                            sf::Vector2i delta = drag_end - left_drag_start;
                            
                            // If it's a small movement on fractal area, treat as zoom
                            if (std::abs(delta.x) < 5 && std::abs(delta.y) < 5 && 
                                event.mouseButton.x < fractal_width) {
                                zoom(event.mouseButton.x, event.mouseButton.y, 0.5);
                                generateFractal();
                                updateTexture();
                                updateInfoText();
                            }
                        }
                    }
                    else if (event.mouseButton.button == sf::Mouse::Right) {
                        right_dragging = false;
                    }
                    break;
                    
                case sf::Event::MouseMoved:
                    if (julia_mode && event.mouseMove.x < fractal_width && 
                        !left_dragging && !right_dragging &&
                        julia_update_clock.getElapsedTime().asSeconds() > julia_update_interval) {
                        // Update Julia constant based on mouse position (with throttling)
                        double real = (double)event.mouseMove.x / fractal_width * 4.0 - 2.0;
                        double imag = (double)event.mouseMove.y / fractal_height * 4.0 - 2.0;
                        julia_c = std::complex<double>(real, imag);
                        
                        generateFractal();
                        updateTexture();
                        updateInfoText();
                        julia_update_clock.restart();
                    } else if (right_dragging && event.mouseMove.x < fractal_width) {
                        // Pan the view with right click + drag
                        sf::Vector2i current_pos(event.mouseMove.x, event.mouseMove.y);
                        sf::Vector2i delta = current_pos - right_drag_start;
                        
                        pan(delta.x, delta.y);
                        right_drag_start = current_pos;
                        
                        generateFractal();
                        updateTexture();
                        updateInfoText();
                    }
                    break;
                    
                case sf::Event::MouseWheelScrolled:
                    if (event.mouseWheelScroll.x < fractal_width) {
                        if (event.mouseWheelScroll.delta > 0) {
                            // Zoom in
                            zoom(event.mouseWheelScroll.x, event.mouseWheelScroll.y, 0.8);
                        } else {
                            // Zoom out
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
        std::cout << "\n=== Interactive Mandelbrot/Julia Set Viewer ===" << std::endl;
        std::cout << "GUI Controls on the right panel" << std::endl;
        std::cout << "Current mode: " << (julia_mode ? "Julia" : "Mandelbrot") << std::endl;
        
        while (window.isOpen()) {
            handleEvents();
            
            window.clear(sf::Color(40, 40, 40));
            
            // Draw fractal
            window.draw(sprite);
            
            // Draw GUI panel background
            sf::RectangleShape gui_panel(sf::Vector2f(200, window_height));
            gui_panel.setPosition(fractal_width, 0);
            gui_panel.setFillColor(sf::Color(30, 30, 30));
            window.draw(gui_panel);
            
            // Draw buttons
            for (size_t i = 0; i < buttons.size(); i++) {
                // Only draw Julia buttons in Julia mode
                if (i >= 6 && i <= 8 && !julia_mode) continue;
                buttons[i].draw(window);
            }
            
            // Draw info text
            window.draw(info_text);
            
            window.display();
        }
    }
};

int main() {
    int width = 800, height = 600;
    
    std::cout << "Enter fractal dimensions (width height) [default 800 600]: ";
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