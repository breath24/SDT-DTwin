import pytest
from connect_four import ConnectFour, SimpleAI, AdvancedAI, GameState

class TestConnectFour:
    """Test cases for ConnectFour game logic."""
    
    def test_init(self):
        """Test game initialization."""
        game = ConnectFour()
        board = game.get_board()
        assert len(board) == 6  # 6 rows
        assert len(board[0]) == 7  # 7 columns
        assert all(cell == ' ' for row in board for cell in row)
    
    def test_custom_dimensions(self):
        """Test custom board dimensions."""
        game = ConnectFour(rows=8, cols=9)
        board = game.get_board()
        assert len(board) == 8
        assert len(board[0]) == 9
    
    def test_valid_move(self):
        """Test valid move detection."""
        game = ConnectFour()
        assert game.is_valid_move(0) == True
        assert game.is_valid_move(6) == True
        assert game.is_valid_move(-1) == False
        assert game.is_valid_move(7) == False
    
    def test_make_move(self):
        """Test making moves."""
        game = ConnectFour()
        
        # First move should go to bottom
        assert game.make_move('X', 0) == True
        board = game.get_board()
        assert board[5][0] == 'X'  # Bottom row, first column
        
        # Second move in same column should stack
        assert game.make_move('O', 0) == True
        board = game.get_board()
        assert board[4][0] == 'O'  # One row up
        assert board[5][0] == 'X'  # Original piece still there
    
    def test_column_full(self):
        """Test behavior when column is full."""
        game = ConnectFour()
        
        # Fill column 0 completely
        for i in range(6):
            player = 'X' if i % 2 == 0 else 'O'
            assert game.make_move(player, 0) == True
        
        # Next move should fail
        assert game.make_move('X', 0) == False
        assert game.is_valid_move(0) == False
    
    def test_horizontal_win(self):
        """Test horizontal win detection."""
        game = ConnectFour()
        
        # Set up horizontal win for X
        for col in range(4):
            game.make_move('X', col)
            if col < 3:  # Don't check on winning move yet
                assert game.check_winner() is None
        
        # Should detect win
        assert game.check_winner() == 'X'
    
    def test_vertical_win(self):
        """Test vertical win detection."""
        game = ConnectFour()
        
        # Set up vertical win for X in column 0
        for row in range(4):
            game.make_move('X', 0)
            if row < 3:
                assert game.check_winner() is None
        
        assert game.check_winner() == 'X'
    
    def test_diagonal_win_ascending(self):
        """Test ascending diagonal win."""
        game = ConnectFour()
        
        # Create ascending diagonal: bottom-left to top-right
        # Column 0: X at bottom
        game.make_move('X', 0)
        
        # Column 1: O, then X  
        game.make_move('O', 1)
        game.make_move('X', 1)
        
        # Column 2: O, O, then X
        game.make_move('O', 2)
        game.make_move('O', 2)
        game.make_move('X', 2)
        
        # Column 3: O, O, O, then X (should win)
        game.make_move('O', 3)
        game.make_move('O', 3)
        game.make_move('O', 3)
        game.make_move('X', 3)
        
        assert game.check_winner() == 'X'
    
    def test_tie_game(self):
        """Test tie detection when board is full."""
        game = ConnectFour(rows=2, cols=2)  # Small board for easier testing
        
        # Fill board without any wins
        game.make_move('X', 0)  # Bottom left
        game.make_move('O', 1)  # Bottom right
        game.make_move('O', 0)  # Top left
        game.make_move('X', 1)  # Top right
        
        assert game.check_winner() == 'tie'
    
    def test_get_valid_moves(self):
        """Test getting list of valid moves."""
        game = ConnectFour()
        
        # Initially all columns should be valid
        valid = game.get_valid_moves()
        assert len(valid) == 7
        assert valid == [0, 1, 2, 3, 4, 5, 6]
        
        # Fill column 0
        for _ in range(6):
            game.make_move('X', 0)
        
        valid = game.get_valid_moves()
        assert 0 not in valid
        assert len(valid) == 6
    
    def test_reset_game(self):
        """Test game reset functionality."""
        game = ConnectFour()
        
        # Make some moves
        game.make_move('X', 0)
        game.make_move('O', 1)
        
        # Reset and verify
        game.reset_game()
        board = game.get_board()
        assert all(cell == ' ' for row in board for cell in row)
        assert len(game.get_valid_moves()) == 7
    
    def test_board_display(self):
        """Test board display functionality."""
        game = ConnectFour()
        game.make_move('X', 0)
        game.make_move('O', 1)
        
        display = game.display_board()
        assert isinstance(display, str)
        assert 'X' in display
        assert 'O' in display
    
    def test_game_stats(self):
        """Test game statistics tracking."""
        game = ConnectFour()
        game.make_move('X', 0)
        game.make_move('O', 1)
        
        stats = game.get_game_stats()
        assert isinstance(stats, dict)
        assert 'moves_made' in stats
        assert stats['moves_made'] >= 2

class TestSimpleAI:
    """Test cases for SimpleAI."""
    
    def test_ai_initialization(self):
        """Test AI initialization."""
        ai = SimpleAI('X')
        assert hasattr(ai, 'player')
    
    def test_ai_makes_valid_move(self):
        """Test that AI makes valid moves."""
        game = ConnectFour()
        ai = SimpleAI('X')
        
        move = ai.get_move(game.get_board())
        assert 0 <= move <= 6
        assert game.is_valid_move(move)
    
    def test_ai_wins_when_possible(self):
        """Test that AI takes winning moves."""
        game = ConnectFour()
        ai = SimpleAI('X')
        
        # Set up a winning opportunity for X
        for col in range(3):
            game.make_move('X', col)
        
        board = game.get_board()
        winning_move = ai.find_winning_move(board, 'X')
        assert winning_move == 3  # Should complete the horizontal line
    
    def test_ai_blocks_opponent_win(self):
        """Test that AI blocks opponent wins."""
        game = ConnectFour()
        ai = SimpleAI('X')
        
        # Set up winning opportunity for O
        for col in range(3):
            game.make_move('O', col)
        
        board = game.get_board()
        blocking_move = ai.block_opponent_win(board, 'X')
        assert blocking_move == 3  # Should block O's winning move
    
    def test_evaluate_position(self):
        """Test position evaluation."""
        game = ConnectFour()
        ai = SimpleAI('X')
        
        # Empty board should have neutral evaluation
        board = game.get_board()
        score = ai.evaluate_position(board, 'X')
        assert isinstance(score, int)

class TestAdvancedAI:
    """Test cases for AdvancedAI."""
    
    def test_advanced_ai_initialization(self):
        """Test advanced AI initialization."""
        ai = AdvancedAI('O')
        assert hasattr(ai, 'player')
    
    def test_advanced_ai_makes_valid_move(self):
        """Test that advanced AI makes valid moves."""
        game = ConnectFour()
        ai = AdvancedAI('O')
        
        move = ai.get_move(game.get_board())
        assert 0 <= move <= 6
        assert game.is_valid_move(move)
    
    def test_minimax_depth(self):
        """Test minimax with different depths."""
        game = ConnectFour()
        ai = AdvancedAI('O')
        
        # Should be able to handle different depths
        move1 = ai.get_move(game.get_board(), depth=1)
        move2 = ai.get_move(game.get_board(), depth=3)
        
        assert 0 <= move1 <= 6
        assert 0 <= move2 <= 6
    
    def test_board_evaluation(self):
        """Test board evaluation function."""
        game = ConnectFour()
        ai = AdvancedAI('O')
        
        # Test evaluation on empty board
        board = game.get_board()
        score = ai.evaluate_board(board)
        assert isinstance(score, int)
        
        # Test evaluation after some moves
        game.make_move('O', 3)  # Center column should be valued
        board = game.get_board()
        score_after = ai.evaluate_board(board)
        assert isinstance(score_after, int)

class TestGameIntegration:
    """Integration tests for complete game scenarios."""
    
    def test_complete_game_x_wins(self):
        """Test a complete game where X wins."""
        game = ConnectFour()
        
        # X wins horizontally
        moves = [
            ('X', 0), ('O', 0),
            ('X', 1), ('O', 1), 
            ('X', 2), ('O', 2),
            ('X', 3)  # X wins
        ]
        
        for player, col in moves[:-1]:
            game.make_move(player, col)
            assert game.check_winner() is None
        
        # Final winning move
        game.make_move('X', 3)
        assert game.check_winner() == 'X'
    
    def test_ai_vs_ai_game(self):
        """Test AI vs AI game completion."""
        game = ConnectFour()
        ai1 = SimpleAI('X')
        ai2 = SimpleAI('O')
        
        current_player = 'X'
        moves = 0
        max_moves = 42  # Maximum possible moves
        
        while game.check_winner() is None and moves < max_moves:
            if current_player == 'X':
                move = ai1.get_move(game.get_board())
            else:
                move = ai2.get_move(game.get_board())
            
            success = game.make_move(current_player, move)
            assert success, f"Invalid move by AI: {move}"
            
            current_player = 'O' if current_player == 'X' else 'X'
            moves += 1
        
        # Game should end in reasonable number of moves
        result = game.check_winner()
        assert result in ['X', 'O', 'tie']
