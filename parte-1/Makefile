CXX = c++
CXXFLAGS = -O3 -Wall -Wextra -std=c++17

TARGET = sol-1
SRC = main.cpp

all: $(TARGET)

$(TARGET): $(SRC) estado.hpp abierta.hpp cerrada.hpp grafo.hpp
	$(CXX) $(CXXFLAGS) $(SRC) -o $(TARGET)

delete:
	rm -f $(TARGET)

.PHONY: all delete
