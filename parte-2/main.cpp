
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "estado.hpp"
#include "grafo.hpp"
#include "abierta.hpp"
#include "cerrada.hpp"

namespace airport_search {

struct SearchResult {
    double distance;
    std::vector<std::string> route;
};

// Splits a CSV line, taking quoted fields into account.
std::vector<std::string> split_csv(const std::string& line) {
    std::vector<std::string> fields;
    std::string field;
    bool inside_quotes = false;

    for (std::size_t i = 0; i < line.size(); ++i) {
        const char c = line[i];

        if (c == '"') {
            if (inside_quotes && i + 1 < line.size() && line[i + 1] == '"') {
                field += '"';
                ++i;
            } else {
                inside_quotes = !inside_quotes;
            }
        } else if (c == ',' && !inside_quotes) {
            fields.push_back(field);
            field.clear();
        } else {
            field += c;
        }
    }

    if (inside_quotes) {
        throw std::runtime_error("Unclosed quotation mark in CSV row.");
    }

    fields.push_back(field);
    return fields;
}

// Removes whitespace from the beginning and end of a string.
std::string trim(const std::string& value) {
    const std::size_t first = value.find_first_not_of(" \t\r\n");

    if (first == std::string::npos) {
        return "";
    }

    const std::size_t last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

// Reads a numeric field and checks that the entire field is valid.
double parse_coordinate(
    const std::string& value,
    const std::string& filename,
    std::size_t line_number
) {
    const std::string cleaned = trim(value);

    if (cleaned.empty()) {
        throw std::runtime_error(
            filename + ":" + std::to_string(line_number) +
            ": empty coordinate."
        );
    }

    try {
        std::size_t parsed_characters = 0;
        const double number = std::stod(cleaned, &parsed_characters);

        if (parsed_characters != cleaned.size() || !std::isfinite(number)) {
            throw std::runtime_error("Invalid coordinate.");
        }

        return number;

    } catch (const std::exception&) {
        throw std::runtime_error(
            filename + ":" + std::to_string(line_number) +
            ": invalid coordinate '" + cleaned + "'."
        );
    }
}

// Checks that a CSV file has the expected initial column names.
void validate_header(
    const std::vector<std::string>& fields,
    const std::vector<std::string>& expected,
    const std::string& filename
) {
    if (fields.size() < expected.size()) {
        throw std::runtime_error(
            filename + ": missing or invalid CSV header."
        );
    }

    for (std::size_t i = 0; i < expected.size(); ++i) {
        if (trim(fields[i]) != expected[i]) {
            throw std::runtime_error(
                filename + ": unexpected column '" + trim(fields[i]) +
                "' at position " + std::to_string(i + 1) +
                "; expected '" + expected[i] + "'."
            );
        }
    }
}

// Loads airports and their coordinates from vertices.csv.
void load_airports(AirportGraph& graph, const std::string& filename) {
    std::ifstream file(filename);

    if (!file) {
        throw std::runtime_error("Could not open " + filename);
    }

    std::string line;

    if (!std::getline(file, line)) {
        throw std::runtime_error(filename + ": empty CSV file.");
    }

    // Expected initial columns:
    // acronym,longitude_deg,latitude_deg
    validate_header(
        split_csv(line),
        {"acronym", "longitude_deg", "latitude_deg"},
        filename
    );

    std::size_t line_number = 1;
    std::size_t loaded_airports = 0;

    while (std::getline(file, line)) {
        ++line_number;

        if (trim(line).empty()) {
            continue;
        }

        try {
            const auto fields = split_csv(line);

            if (fields.size() < 3) {
                throw std::runtime_error("Missing airport fields.");
            }

            const std::string code = trim(fields[0]);

            if (code.size() != 3) {
                throw std::runtime_error(
                    "Airport code must contain exactly three characters."
                );
            }

            // CSV order is longitude first, latitude second.
            const double longitude = parse_coordinate(
                fields[1], filename, line_number
            );

            const double latitude = parse_coordinate(
                fields[2], filename, line_number
            );

            if (longitude < -180.0 || longitude > 180.0) {
                throw std::runtime_error("Longitude outside valid range.");
            }

            if (latitude < -90.0 || latitude > 90.0) {
                throw std::runtime_error("Latitude outside valid range.");
            }

            graph.add_airport(
                AirportState(code, latitude, longitude)
            );

            ++loaded_airports;

        } catch (const std::exception& error) {
            throw std::runtime_error(
                filename + ":" + std::to_string(line_number) +
                ": " + error.what()
            );
        }
    }

    if (loaded_airports == 0) {
        throw std::runtime_error(filename + ": no airports were loaded.");
    }
}

// Loads directed flight connections from edges.csv.
void load_edges(AirportGraph& graph, const std::string& filename) {
    std::ifstream file(filename);

    if (!file) {
        throw std::runtime_error("Could not open " + filename);
    }

    std::string line;

    if (!std::getline(file, line)) {
        throw std::runtime_error(filename + ": empty CSV file.");
    }

    // Expected initial columns:
    // origin,destination
    validate_header(
        split_csv(line),
        {"origin", "destination"},
        filename
    );

    std::size_t line_number = 1;
    std::size_t loaded_edges = 0;

    while (std::getline(file, line)) {
        ++line_number;

        if (trim(line).empty()) {
            continue;
        }

        try {
            const auto fields = split_csv(line);

            if (fields.size() < 2) {
                throw std::runtime_error("Missing edge fields.");
            }

            const std::string origin = trim(fields[0]);
            const std::string destination = trim(fields[1]);

            if (origin.size() != 3 || destination.size() != 3) {
                throw std::runtime_error(
                    "Airport codes must contain exactly three characters."
                );
            }

            // add_neighbour checks that both airports exist.
            graph.add_neighbour(origin, destination);

            ++loaded_edges;

        } catch (const std::exception& error) {
            throw std::runtime_error(
                filename + ":" + std::to_string(line_number) +
                ": " + error.what()
            );
        }
    }

    if (loaded_edges == 0) {
        throw std::runtime_error(filename + ": no edges were loaded.");
    }
}

// Reconstructs the route by following the parent pointers.
std::vector<std::string> reconstruct_route(
    const OpenList::NodePtr& goal_node
) {
    std::vector<std::string> route;

    for (auto node = goal_node; node != nullptr; node = node->parent) {
        const auto& code = node->state.get_IATA();
        route.emplace_back(code.begin(), code.end());
    }

    std::reverse(route.begin(), route.end());
    return route;
}

// Shared search implementation.
// With use_heuristic = false, it performs Dijkstra.
// With use_heuristic = true, it performs A*.
SearchResult best_first_search(
    const AirportGraph& graph,
    const AirportState& start,
    const AirportState& goal,
    bool use_heuristic
) {
    OpenList open;
    ClosedList closed;

    // Stores the best accumulated distance found for each airport.
    std::unordered_map<AirportState, double> best_g;

    const double initial_h = use_heuristic
        ? haversine(start, goal)
        : 0.0;

    auto initial_node = std::make_shared<SearchNode>(
        start,
        nullptr,
        0.0,
        initial_h
    );

    open.push(initial_node);
    best_g[start] = 0.0;

    while (!open.empty()) {
        const auto current = open.pop();

        // Ignore outdated entries in the open list.
        const auto best_it = best_g.find(current->state);

        if (best_it == best_g.end() || current->g > best_it->second) {
            continue;
        }

        // Each airport is expanded only once.
        if (!closed.insert(current->state)) {
            continue;
        }

        // The destination has been reached.
        if (current->state == goal) {
            return {
                current->g,
                reconstruct_route(current)
            };
        }

        // Explore all directly connected airports.
        for (const auto& [neighbour, edge_cost] :
             graph.successors(current->state)) {

            if (closed.contains(neighbour)) {
                continue;
            }

            const double new_g = current->g + edge_cost;

            const auto it = best_g.find(neighbour);

            // Ignore paths that are not better than the current one.
            if (it != best_g.end() && new_g >= it->second) {
                continue;
            }

            best_g[neighbour] = new_g;

            const double h = use_heuristic
                ? haversine(neighbour, goal)
                : 0.0;

            auto neighbour_node = std::make_shared<SearchNode>(
                neighbour,
                current,
                new_g,
                h
            );

            open.push(neighbour_node);
        }
    }

    throw std::runtime_error(
        "No route exists between the selected airports."
    );
}

// Uninformed search: Dijkstra's algorithm.
// Priority = g(n).
SearchResult dijkstra(
    const AirportGraph& graph,
    const AirportState& start,
    const AirportState& goal
) {
    return best_first_search(graph, start, goal, false);
}

// Heuristic search: A*.
// Priority = g(n) + h(n), where h(n) is the Haversine distance.
SearchResult a_star(
    const AirportGraph& graph,
    const AirportState& start,
    const AirportState& goal
) {
    return best_first_search(graph, start, goal, true);
}

// Reads the origin and destination from the input file.
std::pair<std::string, std::string> read_input(
    const std::string& filename
) {
    std::ifstream file(filename);

    if (!file) {
        throw std::runtime_error(
            "Could not open input file: " + filename
        );
    }

    std::string origin;
    std::string destination;

    if (!std::getline(file, origin) || !std::getline(file, destination)) {
        throw std::runtime_error(
            "Input file must contain two airport codes."
        );
    }

    origin = trim(origin);
    destination = trim(destination);

    if (origin.empty() || destination.empty()) {
        throw std::runtime_error("Airport codes cannot be empty.");
    }

    return {origin, destination};
}

// Writes the required two-line result.
void write_result(
    std::ostream& output,
    const SearchResult& result
) {
    output << std::fixed << std::setprecision(2);
    output << result.distance << '\n';

    for (std::size_t i = 0; i < result.route.size(); ++i) {
        if (i > 0) {
            output << " - ";
        }

        output << result.route[i];
    }

    output << '\n';
}

} // namespace airport_search

int main(int argc, char* argv[]) {
    using namespace airport_search;

    if (argc != 3) {
        std::cerr << "Usage: " << argv[0]
                  << " <input_file> <output_file>\n";
        return 1;
    }

    try {
        // Read the origin and destination.
        const auto [origin_code, destination_code] = read_input(argv[1]);

        // Load the airport graph.
        AirportGraph graph;

        load_airports(graph, "vertices.csv");
        load_edges(graph, "edges.csv");

        // Check that both airports exist.
        if (!graph.contains(origin_code)) {
            throw std::runtime_error(
                "Unknown origin airport: " + origin_code
            );
        }

        if (!graph.contains(destination_code)) {
            throw std::runtime_error(
                "Unknown destination airport: " + destination_code
            );
        }

        const AirportState& origin = graph.get_airport(origin_code);
        const AirportState& destination = graph.get_airport(destination_code);

        const SearchResult result = a_star(graph, origin, destination);

        std::ofstream output(argv[2]);

        if (!output) {
            throw std::runtime_error(
                "Could not open output file: " + std::string(argv[2])
            );
        }

        // Write the same two-line result to the file and standard output.
        write_result(output, result);
        write_result(std::cout, result);

        return 0;

    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << '\n';
        return 1;
    }
}
