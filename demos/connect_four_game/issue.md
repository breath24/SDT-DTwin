# Implement Connect Four Game Engine

Create a complete Connect Four game implementation in `connect_four.py` with the following components:

## Core Game Classes
1. **`ConnectFour` class** - Main game engine with:
   - `__init__(rows=6, cols=7)` - Initialize game board
   - `make_move(player, column)` - Drop piece in column (returns success/failure)
   - `check_winner()` - Check for winner (returns 'X', 'O', 'tie', or None)
   - `is_valid_move(column)` - Check if column move is valid
   - `get_board()` - Return current board state
   - `reset_game()` - Reset to initial state
   - `get_valid_moves()` - Return list of valid column numbers

2. **`GameState` enum** - Game state tracking (PLAYING, X_WINS, O_WINS, TIE)

## AI Components
1. **`SimpleAI` class** - Basic AI opponent with:
   - `get_move(board)` - Return best column choice
   - `evaluate_position(board, player)` - Score board position
   - `find_winning_move(board, player)` - Find immediate winning move
   - `block_opponent_win(board, player)` - Block opponent's winning move

2. **`AdvancedAI` class** - Minimax AI with:
   - `get_move(board, depth=4)` - Minimax with alpha-beta pruning
   - `minimax(board, depth, alpha, beta, maximizing_player)` - Minimax algorithm
   - `evaluate_board(board)` - Advanced position evaluation

## Game Features
1. **Win Detection**: Implement detection for:
   - Horizontal wins (4 in a row)
   - Vertical wins (4 in a column)  
   - Diagonal wins (both directions)

2. **Board Display**: 
   - `display_board()` - ASCII art board visualization
   - `board_to_string()` - String representation for testing

3. **Game Statistics**:
   - Track moves made, game duration
   - `get_game_stats()` - Return game statistics dictionary

Include input validation, error handling, and comprehensive documentation. The AI should be challenging but not unbeatable. Make all tests pass with `python -m pytest`.
