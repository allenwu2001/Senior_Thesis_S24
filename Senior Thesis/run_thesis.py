import os
import chess
import chess.engine
import pandas as pd
pd.options.mode.chained_assignment = None  # default='warn'
pd.set_option('display.max_columns', None)
import numpy as np
import asyncio
from collections import defaultdict
import time

########### START FUNCTIONS
# use this_fen to count pieces of each player (white is uppercase, black is lowercase)
# we want to calculate material_change in depth of 5 in stockfish's line of pv, as opposed to the actual sequence here
# (this is similar to what I do in stockfish but return 5 moves instead of 1 recommended move), then loop through 5 moves and
# calculate material change delta (return both players material changes in a tuple for each index) --> (active, inactive) format
def material(last_board, board, active_player):
    this_fen = board.fen()
    this_white_material, this_black_material = 0, 0
    for i in range(len(this_fen)):
        char = this_fen[i]
        if char == " ":
            break
        elif char == "/" or char.isnumeric() or char == "k" or char == "K":
            continue
        elif char.islower():
            if char == "p":
                this_black_material += 1
            elif char == "r":
                this_black_material += 5
            elif char == "n":
                this_black_material += 3
            elif char == "b":
                this_black_material += 4
            else:
                this_black_material += 9
        else:
            if char == "P":
                this_white_material += 1
            elif char == "R":
                this_white_material += 5
            elif char == "N":
                this_white_material += 3
            elif char == "B":
                this_white_material += 4
            else:
                this_white_material += 9
#     print(this_fen)
#     print(this_white_material, this_black_material)
        
    last_fen = last_board.fen()
    last_white_material, last_black_material = 0, 0
    for i in range(len(last_fen)):
        char = last_fen[i]
        if char == " ":
            break
        elif char == "/" or char.isnumeric() or char == "k" or char == "K":
            continue
        elif char.islower():
            if char == "p":
                last_black_material += 1
            elif char == "r":
                last_black_material += 5
            elif char == "n":
                last_black_material += 3
            elif char == "b":
                last_black_material += 4
            else:
                last_black_material += 9
        else:
            if char == "P":
                last_white_material += 1
            elif char == "R":
                last_white_material += 5
            elif char == "N":
                last_white_material += 3
            elif char == "B":
                last_white_material += 4
            else:
                last_white_material += 9
#     print(last_fen)
#     print(last_white_material, last_black_material)
                
    white_change = last_white_material - this_white_material
    black_change = last_black_material - this_black_material
    # if white_move made, only black_material can change and vice versa
    if active_player == "white":
        return black_change
    return white_change

def delta_material(stockfish_moves, current_board, active_player):
    active_delta_material, opponent_delta_material = [], []
    board = current_board.copy()
    
    for i in range(len(stockfish_moves)):
        last_board = board.copy()
        board.push_uci(stockfish_moves[i].uci())
        
        this_active_player = ""
        # all even moves = stockfish-recommended moves for the active_player
        if i % 2 == 0:
            this_active_player = active_player
            material_change = material(last_board, board, this_active_player)
            opponent_delta_material.append(material_change)
        else:
            if active_player == "white":
                this_active_player = "black"
            else:
                this_active_player = "white"
            
            material_change = material(last_board, board, this_active_player)
            active_delta_material.append(material_change)
            
    return [active_delta_material, opponent_delta_material]

# modified original approach to only print highest depth return info
# need to generalize this to take in any given current_board
def stockfish(current_board, desired_depth=15, num_moves=6):
    info = engine.analyse(current_board, chess.engine.Limit(depth=desired_depth))
    stockfish_pv = info['pv']
    stockfish_eval_score = info['score'].relative.score()
    return (stockfish_pv[0:num_moves], stockfish_eval_score)

def collect_data(data, n_moves_remaining, initial_start, desired_depth=15, num_moves=6):
    # returns (delta_materials, move_match) --> tuple(2d matrix, 1d vector)
    delta_materials, move_match = [], []
    
    for i, move in enumerate(data['move'][:n_moves_remaining]):
        # print each move_idx and print time taken for every 1000 (keep process accountable)
        start = time.time()
        
        if (i%10 == 0):
            print(i, end = ' ')
            
        if (i%1000 == 0):
            curr_time = (time.time()-initial_start)/3600;
            print(str(np.round(curr_time,decimals = 2))+' hours so far')
        
        this_row = data.iloc[i,:]
        this_fen, this_white_active = this_row.board, this_row.white_active
        current_board = chess.Board(this_fen)
        active_player = "white" if this_white_active else "black"
        
        # stockfish_tuple = (stockfish_moves, stockfish_score)
        # stockfish_score unused now, but may use later as another heuristic
        stockfish_tuple = stockfish(current_board, desired_depth, num_moves)
        stockfish_moves, stockfish_score = stockfish_tuple[0], stockfish_tuple[1]
        
        delta_material_tuple = delta_material(stockfish_moves, current_board, active_player)
        active_delta_material, opponent_delta_material = delta_material_tuple[0], delta_material_tuple[1]
        
        if len(active_delta_material) == 3 and len(opponent_delta_material) == 3:
            delta_materials.append([active_delta_material, opponent_delta_material])

            stockfish_move = stockfish_moves[0]
            if str(stockfish_move) == str(move):
                move_match.append(1)
            else:
                move_match.append(0)
            
        # check opponent move against first stockfish move too
        # HAVING PROBLEMS WITH THIS: 
#         opponent_move = data['move'][i+1]
#         current_board.push_uci(stockfish_move.uci())
#         stockfish_opponent_move = stockfish(current_board, desired_depth, num_moves)[0][0]
#         if str(stockfish_opponent_move) == str(opponent_move):
#             move_match.append(1)
#         else:
#             move_match.append(0)
            
    return [delta_materials, move_match]


def translate_delta_materials(delta_materials):
    translated_delta_materials = []
    piece_offset_hm = {0: 0, 1: 1, 3: 2, 4: 3, 5: 4, 9: 5}      # gives correct index in len-36 vector

    for delta_materials_row in delta_materials:
        translated_row = [0 for j in range(36)]
        active_delta, opponent_delta = delta_materials_row[0], delta_materials_row[1]

        # associated with opponent moves: 0 -> 6, 1 -> 18, 2 -> 30
        for i, val in enumerate(active_delta):
            vec_i = (6 + i*12) + piece_offset_hm[val]
            translated_row[vec_i] = 1

        # associated with active moves: 0 -> 0, 1 -> 12, 2 -> 24
        for i, val in enumerate(opponent_delta):
            vec_i = (i*12) + piece_offset_hm[val]
            translated_row[vec_i] = 1

        translated_delta_materials.append(translated_row)
        
    return translated_delta_materials


########### END FUNCTIONS 
if __name__ == "__main__":
    # set folders
    is_array_job = True
    
    # get array job number if it's part of an array job
    if is_array_job:
        job_idx = int(os.environ["SLURM_ARRAY_TASK_ID"]) - 1
    # else get random index > max job num (handling a single task)
    else:
        job_idx = 5
    
    # code runs on cluster environment
    working_folder = '/home/allenwu/Senior Thesis'
    stockfish_path = "/home/allenwu/Senior Thesis/stockfish_14.1_linux_x64_avx2/stockfish_14.1_linux_x64_avx2"
    chess_csv_file = '/scratch/gpfs/allenwu/lichess_db_standard_rated_2019-01.csv'
    # may need to change this?
    to_save_folder = '/scratch/gpfs/allenwu/analysis_results_Mar_2023_cluster_4_only_time_bullet'
    
    os.chdir(working_folder)
    
    # set which moves/rows to load and run (may need to increase this to scale)
    moves_per_run = 30000
    n_total_runs = 300
    start_move = 0
    
    # builds 2d array with dimensions [n_total_runs, moves_per_run]
    run_by_idxs = np.reshape(np.arange(moves_per_run*n_total_runs), (n_total_runs, moves_per_run))
    # gets the "job_idx"'s run
    run_idxs = run_by_idxs[job_idx,:]
    print("run_idxs:", run_idxs, np.shape(run_idxs))
    
    # load in data for this job (should include both a folder and a # of rows)
    data_first = pd.read_csv(chess_csv_file, nrows=2)
    cols = data_first.columns
    data = pd.read_csv(chess_csv_file, skiprows=run_idxs[0]+1, nrows=moves_per_run, names=cols)
    print("data shape:", data.shape)
    
    # filter data by elo rating (will cause each job index's 
    filtered_data_time_bullet = data[(data['time_control'] == '60+0')]
    print("filtered data shape:", filtered_data_time_bullet.shape)
    
    # where should we save the data?
    if not os.path.exists(to_save_folder):
        os.makedirs(to_save_folder)
        
    # make folders for and time_constraints and elo ranges --> secondary folders we may want to save specifically filtered info? --> LATER USE(?)
    # time_constraints_folder = os.path.join(to_save_folder, 'time_constraints')
    # elo_ranges_folder = os.path.join(to_save_folder, 'elo_ranges')
    # if not os.path.exists(time_constraints_folder):
    #     os.makedirs(time_constraints_folder)
    # if not os.path.exists(elo_ranges_folder):
    #     os.makedirs(elo_ranges_folder)

    # remove first move of each player (idt we want this anymore... results in inconsistent shapes across job indices)
    # data = data_raw.loc[data_raw.move_ply > 2].reset_index(drop=True)
    # print("final data shape:", data.shape)
    
    # further filter by game types we care about --> LATER USE(?) --> similarly for elo
    # game_time_types = ['60+0', '120+1', '180+0',
    #                    '180+2', '300+0', '300+3',
    #                    '600+0', '600+5', '900+10',
    #                    '1800+0', '1800+20']
    # data = data.loc[data_filt.time_control.isin(game_time_types)].reset_index(drop = True)
    
    # engine setup
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    
    # loop through respective moves/rows of job in data thorugh collect_data() step
    n_moves_remaining = filtered_data_time_bullet.shape[0]
    print("n_moves_remaining:", n_moves_remaining)
    # print("n_moves_remaining:", n_moves_remaining)
    initial_start = time.time()
    delta_materials, move_match = collect_data(filtered_data_time_bullet, n_moves_remaining, initial_start)
    
    # translated_delta_materials = translate_delta_materials(delta_materials)
    
    # save [delta_materials, move_match] result from curr job_idx's run in a new file
    start_idx, end_idx = run_idxs[0], run_idxs[-1]
    delta_materials_file_name = 'job_'+str(job_idx)+'_start_'+str(start_idx)+'_end_'+str(end_idx)+'_delta_materials'+'.npy'
    # save to to_save_folder directly for now (but eventually save to time/elo-specific folders)
    with open(os.path.join(to_save_folder, delta_materials_file_name), 'wb') as f:
              print("Shape of delta_materials:", np.array(delta_materials, dtype=object).shape)
              np.save(f, np.array(delta_materials, dtype=object))
              
    move_match_file_name = 'job_'+str(job_idx)+'_start_'+str(start_idx)+'_end_'+str(end_idx)+'_move_match'+'.npy'
    with open(os.path.join(to_save_folder, move_match_file_name), 'wb') as f:
              print("Shape of move_match:", np.array(move_match).shape)
              np.save(f, np.array(move_match))
    
    # close the chess engine
    engine.quit()
    print('script is done!')