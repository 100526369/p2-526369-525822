
#ifndef ABIERTA_HPP
#define ABIERTA_HPP

#include <cstddef>
#include <cstdint>
#include <memory>
#include <queue>
#include <stdexcept>
#include <utility>
#include <vector>

#include "estado.hpp"

namespace airport_search {

// A search node contains the state and its search information
struct SearchNode {

    AirportState state;

    // Parent node used to reconstruct the solution path
    std::shared_ptr<const SearchNode> parent;

    // Accumulated cost from the initial state
    double g;

    // Heuristic estimate of the remaining cost to the goal
    double h;

    SearchNode(
        const AirportState& airport_state,
        std::shared_ptr<const SearchNode> parent_node,
        double accumulated_cost,
        double heuristic
    )
        : state(airport_state),
          parent(std::move(parent_node)),
          g(accumulated_cost),
          h(heuristic)
    {}

    // Evaluation function: f(n) = g(n) + h(n)
    double f() const {
        return g + h;
    }
};

class OpenList {
public:

    using NodePtr = std::shared_ptr<const SearchNode>;

    // Checks whether the open list is empty
    bool empty() const {
        return nodes_.empty();
    }

    // Returns the number of nodes in the open list
    std::size_t size() const {
        return nodes_.size();
    }

    // Inserts a node according to its evaluation function
    void push(NodePtr node) {

        if (!node) {
            throw std::invalid_argument(
                "Cannot insert a null node into the open list"
            );
        }

        // Store f and g because the node is immutable
        const double priority = node->f();
        const double accumulated_cost = node->g;

        nodes_.push({
            priority,
            accumulated_cost,
            next_order_++,
            std::move(node)
        });
    }

    // Removes and returns the node with the smallest f value
    NodePtr pop() {

        if (empty()) {
            throw std::out_of_range(
                "Cannot remove a node from an empty open list"
            );
        }

        NodePtr node = nodes_.top().node;
        nodes_.pop();

        return node;
    }

private:

    struct Entry {
        double priority;
        double g;
        std::uint64_t order;
        NodePtr node;
    };

    // Priority queue comparator:
    // 1. Smallest f first.
    // 2. Largest g first when f values are equal.
    // 3. Oldest node first when both f and g are equal.
    struct Compare {

        bool operator()(
            const Entry& a,
            const Entry& b
        ) const {

            if (a.priority != b.priority) {
                return a.priority > b.priority;
            }

            if (a.g != b.g) {
                return a.g < b.g;
            }

            return a.order > b.order;
        }
    };

    std::priority_queue<
        Entry,
        std::vector<Entry>,
        Compare
    > nodes_;

    std::uint64_t next_order_ = 0;
};

} // namespace airport_search

#endif // ABIERTA_HPP
