# Design Patterns in Spyder Okvim

This project applies several object-oriented design patterns to remain flexible while following the SOLID principles.

## Decorator Pattern

The `submode` decorator in `spyder_okvim/executor/decorators.py` wraps command methods so they can easily enter a submode without repeating boilerplate. This keeps each command focused on its own behavior (Single Responsibility) while making it easy to extend with new submodes (Open/Closed).

## Command Pattern

Each executor class (`ExecutorNormalCmd`, `ExecutorVisualCmd`, etc.) interprets keystrokes as commands. Every method that handles a key acts as an individual command object. This organization makes it simple to add or override behavior for a specific mode without affecting others.

## Strategy Pattern

Movement and action logic is delegated to helper classes (`HelperMotion`, `HelperAction`). Executors choose which helper method to call depending on the command, enabling different strategies for cursor movement or text manipulation.

By separating concerns across these components, the codebase remains modular and adheres to the SOLID principles of single responsibility and open/closed design.
