import numpy as np
import random

class Robot(object):
    
    # INITIALIZE ROBOT
    #def __init__(self, maze_dim, start_location, start_heading):
    def __init__(self, maze_dim):
        
        # Robot constants
        self.maze_dim = maze_dim
        self.maze_reward = -10
        self.goals = []
        
        self.threshold = self.maze_dim/2
        
        # Mapping of robot's local coordinate system to global maze coordinate system
        self.dir_sensors = {'u': ['l', 'u', 'r'], 'r': ['u', 'r', 'd'],
           'd': ['r', 'd', 'l'], 'l': ['d', 'l', 'u']}
        self.dir_mapping = {'u': ['l', 'u', 'r','d'], 'r': ['u', 'r', 'd','l'],
           'd': ['r', 'd', 'l','u'], 'l': ['d', 'l', 'u','r']}
        self.dir_move = {'u': [0, 1], 'r': [1, 0], 'd': [0, -1], 'l': [-1, 0]}
        self.dir_reverse = {'u': 'd', 'r': 'l', 'd': 'u', 'l': 'r',
           'up': 'd', 'right': 'l', 'down': 'u', 'left': 'r'}
        
        # Present info
        self.move_count = 0
        self.current_location = (0,0)
        self.heading = "u"
        self.found_goal = False
        self.finished_exploring = False
        self.run = 1
        
        # Memory
        self.U_table_to_goal = np.zeros((self.maze_dim,self.maze_dim))
        self.U_table_to_start = np.zeros((self.maze_dim,self.maze_dim))
        self.times_visited = np.zeros((self.maze_dim,self.maze_dim))
        self.path_taken = [self.current_location]
        self.heading_history = [self.heading]
        self.path_taken_to_goal = [self.current_location]
        self.path_taken_to_start = []
        self.next_locations_table = dict()
        self.dead_ends = []
        self.best_path = []
        self.goal = 0
        
        ##TEMP###
        self.loneliness_mat = np.zeros((self.maze_dim,self.maze_dim))
        self.u_table_temp = np.zeros((self.maze_dim,self.maze_dim))
        self.goal_temp = (0,0)
        self.found_loneliest_loc = False
        
        # Create tables and list
        self.initialize_tables()
    
    def initialize_tables(self):
        
        # Cell utilities for heading to goal from start
        
        for x in [i for i in range(-self.maze_dim/2,self.maze_dim/2+1) if i != 0]:
            for y in [j for j in range(-self.maze_dim/2,self.maze_dim/2+1) if j != 0]:
                if x < 0: 
                    dx = self.maze_dim/2 
                else: 
                    dx = self.maze_dim/2 - 1
                if y < 0:
                    dy = self.maze_dim/2
                else:
                    dy = self.maze_dim/2 - 1
                #self.U_table_to_goal[x+dx][y+dy] = (-(abs(x)**2+abs(y)**2)**0.5)
                self.U_table_to_goal[x+dx][y+dy] = (-(abs(x)+abs(y)))+2
        
        # Cell utilities for heading to start from goal
        for x in range(self.maze_dim):
            for y in range(self.maze_dim):
                #create next_locations_table
                self.next_locations_table[(x,y)] = []
                #create utility table for heading back to start of maze
                self.U_table_to_start[(x,y)] = (-x-y)*0.1
        
        # Save goal locations for later
        for x in [-1, 0]:
            for y in [-1,0]:
                self.goals.append((self.maze_dim/2 + x,self.maze_dim/2 + y))

    # HELPER FUNCTIONS
    def get_visible_next_locations(self,sensors):
        valid_moves = []
        valid_moves = list(sensors)
            
        current_location = np.array(self.current_location)
           
        # Convert valid moves to valid locations robot can move to 
        visible_next_locations = []
        for i,val in enumerate(valid_moves):
            if val > 0:
                for x in range(1,val+1):
                    if x <= 3:
                        if self.dir_mapping[self.heading][i] == 'u':
                            visible_next_locations.append(tuple((current_location + [0,x])))
                        elif self.dir_mapping[self.heading][i] == 'd':
                            visible_next_locations.append(tuple(current_location + [0,-x]))
                        elif self.dir_mapping[self.heading][i] == 'l':
                            visible_next_locations.append(tuple(current_location + [-x,0]))
                        else:
                            visible_next_locations.append(tuple(current_location + [x,0]))
                    else:
                        break
                    
        return visible_next_locations

    def get_movements(self, next_location):
        current_location = np.array(self.current_location)
        next_location = np.array(next_location)

        # Get action to get to next location and it's direction
        action = next_location - current_location
        action_dir = list(action/np.linalg.norm(action))
        action_dir = self.dir_move.keys()[self.dir_move.values().index(action_dir)]

        rotation_mapping = [-90,0,90,0]
        rotation = rotation_mapping[self.dir_mapping[self.heading].index(action_dir)]
        
        if rotation==0 and self.heading != action_dir:
            movement = -abs(sum(action))
        else:
            movement = abs(sum(action))
            self.heading = action_dir

        return rotation, movement
      
    def get_backward_locations(self, next_locations):
        
        #if self.move_count > 0: 
        backward_locations = []
        if len(self.path_taken) > 1:
            
            n_steps = 0
            current_location = np.array(self.current_location)
            last_location = np.array(self.path_taken[-2])
            # Get the steps and direction of the last move taken
            last_move = current_location - last_location
            #(remove this) if not sum(last_move)==0:
            last_move_dir = last_move / np.linalg.norm(last_move)
                
            # If last move was a forward step, we can step backward that many steps
            if np.array_equal(last_move_dir,self.dir_move[self.heading]):
                n_steps = abs(sum(last_move))
                dir_bwd_steps = np.array(self.dir_move[self.dir_reverse[self.heading]])
                # Convert number of backward steps to list of locations
                for x in range(1,n_steps+1):
                    backward_locations.append(tuple((current_location + x*dir_bwd_steps)))
            # In the case where we were at a dead end, stepped back one step and once
            # again see no available moves (the cell in front of us has been removed 
            # from the list because it's a dead end) then step back a single cell.
            elif not next_locations:
                bwd_step = np.array(self.dir_move[self.dir_reverse[self.heading]])
                current_location = np.array(self.current_location)
                backward_locations = [tuple(current_location + bwd_step)]    
            return backward_locations
        else:
            return backward_locations
        
    def update_next_locations_table(self,visible_next_locations):
        
        locations_to_add = list(visible_next_locations)
        
        # Remove dead ends from list of available locations
        for dead_end in self.dead_ends:
            for next_location in locations_to_add:
                if next_location == dead_end:
                    locations_to_add.remove(next_location)
        
        # If no visible locations which aren't dead end,
        # consider this cell a dead end also
        if not locations_to_add and self.current_location != (0,0):
            self.remove_dead_end()
        
        
        # Add available locations behind us to list
        locations_to_add += self.get_backward_locations(locations_to_add)

        # Add current location to list
        locations_to_add.append(self.current_location)
        
        # Add locations to next_locations_table which aren't already there
        def add_to_table(locations_to_add,base_loc):
            new_locations_to_add = list(locations_to_add)
            for new_loc in locations_to_add:
                for exist_loc in self.next_locations_table[base_loc]:
                    if new_loc[0] == exist_loc[0] and new_loc[1] == exist_loc[1]:
                            new_locations_to_add.remove(new_loc)
            # Add new locations to next_locations_table
            self.next_locations_table[base_loc] += new_locations_to_add
        
        ###TEMP###
        #locations_to_add.remove(self.current_location)
        #add_to_table(locations_to_add, self.current_location)
        ##########
        
        # Split list into locations along up-down an left-right directions
        up_down_loc = [loc for loc in locations_to_add if loc[0]==self.current_location[0]]
        left_right_loc = [loc for loc in locations_to_add if loc[1]==self.current_location[1]]
        
        # Add locations along a line to all locations in that line
        for line_loc in [up_down_loc,left_right_loc]:
            for base_loc in line_loc:
                copy_line_loc = list(line_loc)
                copy_line_loc.remove(base_loc)
                for loc in line_loc:
                    dist = abs(loc[0]-base_loc[0]) + abs(loc[1]-base_loc[1])
                    if dist > 3:
                        copy_line_loc.remove(loc)
                add_to_table(copy_line_loc,base_loc)
        
    def remove_dead_end(self):
        # Add location to dead end list
        self.dead_ends.append(self.current_location)
        
        # Remove location from next_locations_table
        for location in self.next_locations_table:
            for next_location in self.next_locations_table[location]:
               if next_location == self.current_location:
                    self.next_locations_table[location].remove(next_location)
           
    def get_loneliest_loc(self):

        loneliest_loc = (0,0)
        loneliest_value = 100
        
        def find_loneliness_value(cell):
            mat = np.zeros((self.maze_dim,self.maze_dim))
            visited_mat = np.zeros((self.maze_dim,self.maze_dim))
            for row in range(self.maze_dim):
                for col in range(self.maze_dim):
                    mat[row][col] = 1.0/((abs(row - cell[0]) + abs(col - cell[1]))+1)
                    if self.times_visited[row][col] > 0:
                        visited_mat[row][col] = 1
            return np.sum(visited_mat*mat/np.sum(mat))
        
        for row in range(self.maze_dim):
            for col in range(self.maze_dim):
                self.loneliness_mat[row][col] = find_loneliness_value((row,col))
                if self.loneliness_mat[row][col] < loneliest_value:
                    loneliest_value = self.loneliness_mat[row][col]
                    loneliest_loc = (row,col)
        return loneliest_loc
    
    def update_u_table_temp(self,cell):
        for row in range(self.maze_dim):
            for col in range(self.maze_dim):
                if not (row == cell[0] and col == cell[1]):
                    self.u_table_temp[row][col] = -0.1*(abs(row - cell[0]) + abs(col - cell[1]))
                    
    # THE EXPLORERS
    
    def directed_explorer_of_the_unknown(self):
        
        next_locations = list(self.next_locations_table[self.current_location])
        
        # Find largest utility value
        maxU = -100000
        for location in next_locations:
            if self.U_table_to_goal[location] > maxU:
                maxU = self.U_table_to_goal[location]

        # Make list of all next locations with maxU and choose one
        maxU_locations = []
        for location in next_locations:
            if self.U_table_to_goal[location] == maxU:
                maxU_locations.append(location)
        next_location = random.choice(maxU_locations)
        
        # Add maze reward to utility table to track I've been here
        self.U_table_to_goal[self.current_location] += self.maze_reward
        
        return next_location
        
    def explorer_of_the_unknown(self):
        
        next_locations = list(self.next_locations_table[self.current_location])
        
        min_visited = 100
        for location in next_locations:
            if self.times_visited[location] < min_visited:
                min_visited = self.times_visited[location]
        
        min_visited_locations = []
        for location in next_locations:
            if self.times_visited[location] == min_visited:
                min_visited_locations.append(location)
                
        return random.choice(min_visited_locations) 
     
    def the_curious(self):
        
        next_locations = list(self.next_locations_table[self.current_location])
        
        # Remove goal locations from choices
        copy_next_locations = list(next_locations)
        goal_bounds = [self.maze_dim/2 - 1, self.maze_dim/2]
        for location in next_locations:
            if location[0] in goal_bounds and location[1] in goal_bounds:
                copy_next_locations.remove(location)
        next_locations = copy_next_locations
        
        min_visited = 100
        for location in next_locations:
            if self.times_visited[location] < min_visited:
                min_visited = self.times_visited[location]
        
        min_visited_locations = []
        for location in next_locations:
            if self.times_visited[location] == min_visited:
                min_visited_locations.append(location)
                
        # Find largest utility value
        maxU = -100000
        for location in min_visited_locations:
            if self.U_table_to_start[location] > maxU:
                maxU = self.U_table_to_start[location]

        # Make list of all next locations with maxU and choose one
        maxU_locations = []
        for location in min_visited_locations:
            if self.U_table_to_start[location] == maxU:
                maxU_locations.append(location)
        next_location = random.choice(maxU_locations)
        
        # If next_location is back at start, finish exploring
        if next_location[0] == 0 and next_location[1] == 0:
            self.finished_exploring = True
        
        # Add maze reward to utility table to track I've been here
        self.U_table_to_start[self.current_location] += self.maze_reward
        
        return next_location

     
    def the_reasonably_curious(self):
        
        next_locations = list(self.next_locations_table[self.current_location])
        
        if len(self.path_taken_to_start) > self.threshold:
            for seen_loc in self.path_taken_to_goal:
                if self.current_location[0] == seen_loc[0] and self.current_location[1] == seen_loc[1]:
                    self.finished_exploring = True
                    return
        
        # If you can see the start, end.
        if (0,0) in next_locations:
            self.finished_exploring = True
            return 
        
        # Remove goal locations from choices
        copy_next_locations = list(next_locations)
        goal_bounds = [self.maze_dim/2 - 1, self.maze_dim/2]
        for location in next_locations:
            if location[0] in goal_bounds and location[1] in goal_bounds:
                copy_next_locations.remove(location)
        next_locations = copy_next_locations
                
        # Of the locations left, choose the one with max utility
        maxU = -100000
        for location in next_locations:
            if self.U_table_to_start[location] > maxU:
                maxU = self.U_table_to_start[location]
        maxU_locations = []
        for location in next_locations:
            if self.U_table_to_start[location] == maxU:
                maxU_locations.append(location)
        next_location = random.choice(maxU_locations)
        
        # Add maze reward to utility table to track I've been here
        self.U_table_to_start[self.current_location] += self.maze_reward
        
        self.path_taken_to_start.append(next_location)
        return next_location

    def the_directed_curious(self):
        
        next_locations = list(self.next_locations_table[self.current_location])
        
        if len(self.path_taken_to_start) > self.threshold:
            for seen_loc in self.path_taken_to_goal:
                if self.current_location[0] == seen_loc[0] and self.current_location[1] == seen_loc[1]:
                    self.finished_exploring = True
                    return
        
        # If you can see the loneliest location
        if self.goal_temp in next_locations and not self.found_loneliest_loc:
            self.u_table_temp = self.U_table_to_start
            self.found_loneliest_loc = True
            #for location in self.path_taken_to_start:
            #    self.u_table_temp[location] += self.maze_reward
        
        if (0,0) in next_locations:
            self.finished_exploring = True
            return 
        
        # Remove goal room from choices
        copy_next_locations = list(next_locations)
        goal_bounds = [self.maze_dim/2 - 1, self.maze_dim/2]
        for location in next_locations:
            if location[0] in goal_bounds and location[1] in goal_bounds:
                copy_next_locations.remove(location)
        next_locations = copy_next_locations
                
        # Of the locations left, choose the one with max utility
        maxU = -100000
        for location in next_locations:
            if self.u_table_temp[location] > maxU:
                maxU = self.u_table_temp[location]
        maxU_locations = []
        for location in next_locations:
            if self.u_table_temp[location] == maxU:
                maxU_locations.append(location)
        next_location = random.choice(maxU_locations)
        
        # Add maze reward to utility table to track I've been here
        self.u_table_temp[self.current_location] += self.maze_reward
        
        self.path_taken_to_start.append(next_location)
        return next_location
          
    # THE CHARTER
    def dist_to_finish_estimate(self,maze_dim):
        heuristic_cost_estimate = np.zeros((maze_dim,maze_dim))
        for x in [i for i in range(-maze_dim/2,maze_dim/2+1) if i != 0]:
            for y in [j for j in range(-maze_dim/2,maze_dim/2+1) if j != 0]:
                if x < 0: 
                    dx = maze_dim/2 
                else: 
                    dx = maze_dim/2 - 1
                if y < 0:
                    dy = maze_dim/2
                else:
                    dy = maze_dim/2 - 1
                heuristic_cost_estimate[x+dx][y+dy] = ((abs(x)+abs(y)) - 2)
        return heuristic_cost_estimate

    def a_star(self, start, goal, next_locations, maze_dim):
    
        closedSet = []
        openSet = [start]
        cameFrom = dict()
        heuristic_cost_estimate = self.dist_to_finish_estimate(maze_dim)
            
        gScore = {x:maze_dim**2 for x in next_locations.keys()}
        gScore[start] = 0
        fScore = {x:maze_dim**2 for x in next_locations.keys()}
        fScore[start] = heuristic_cost_estimate[start]
        
        def get_min_fscore(locations):
            location_fScore = [fScore[x] for x in locations]
            min_score = min(location_fScore)
            return locations[location_fScore.index(min_score)]
        
        while openSet:
            
            current = get_min_fscore(openSet)
            
            if current == goal:
                return self.reconstruct_path(cameFrom,current)
            
            openSet.remove(current)
            closedSet.append(current)
            
            
            for next_location in next_locations[current]:
                
                if next_location in closedSet:
                    continue
                
                if next_location not in openSet:
                    openSet.append(next_location)
                        
                tentative_gScore = gScore[current] + 1 
                if tentative_gScore >= gScore[next_location]:
                    continue
                
                cameFrom[next_location] = current
                gScore[next_location] = tentative_gScore
                fScore[next_location] = gScore[next_location] + heuristic_cost_estimate[next_location]

        print "Failed"

    def reconstruct_path(self,cameFrom,current):
        total_path = [current]
        while current in cameFrom.keys():
            current = cameFrom[current]
            total_path.append(current)
        return total_path
    
    # THE DECIDER 
    def next_move(self, sensors):
        
        if self.run == 1:
            self.times_visited[self.current_location] += 1
            
            # Check if current location is the goal
            goal_bounds = [self.maze_dim/2 - 1, self.maze_dim/2]
            if self.current_location[0] in goal_bounds and self.current_location[1] in goal_bounds:
                self.found_goal = True
                self.goal = self.current_location
                self.path_taken_to_goal = list(self.path_taken)
                self.best_path = self.a_star((0,0),self.goal,self.next_locations_table,self.maze_dim)
                # # Add negative reward to previously explored locations
                # for r,row in enumerate(self.times_visited):
                    # for c,col in enumerate(row):
                        # if col > 0:
                            # self.U_table_to_start[r][c] += self.maze_reward/2
                # prep for directed curious
                self.goal_temp = self.get_loneliest_loc()
                self.update_u_table_temp(self.goal_temp)
            
            # Get valid next locations
            visible_next_locations = self.get_visible_next_locations(sensors)

            # Get all valid next locations
            self.update_next_locations_table(visible_next_locations)

            if not self.found_goal:
                
                # THE FOOL
                # chooses where to go randomly
                #next_location = random.choice(list(self.next_locations_table[self.current_location]))
                
                # THE EXPLORER OF THE UNKNOWN
                # Heads towards the unexplored, ignorant of where the center is
                #next_location = self.explorer_of_the_unknown()

                # THE DIRECTED EXPLORER OF THE UNKNOWN
                # Heads towards centre and prefers less explored areas
                next_location = self.directed_explorer_of_the_unknown()
            
            else:
                
                # THE CURIOUS EXPLORER
                # After finding goal, continues exploring for an alternate path
                #next_location = self.the_curious()
                #self.path_taken_to_start.append(next_location)
                
                # THE REASONABLY CURIOUS EXPLORER
                # After finding goal, continues exploring for an alternate path
                #next_location = self.the_reasonably_curious()
                
                # THE DIRECTED CURIOUS
                next_location = self.the_directed_curious()
                
                # THE IMPATIENT EXPLORER
                # is happy to be out of the maze and go to bed
                #self.finished_exploring = True
            
            if self.finished_exploring:
                rotation, movement = ('Reset','Reset')
                new_best_path = self.a_star((0,0),self.goal,self.next_locations_table,self.maze_dim)
                if len(new_best_path) < len(self.best_path):
                    self.best_path = new_best_path
                self.current_location = (0,0)
                self.heading = 'u'
                self.run = 2
            else:
                rotation, movement = self.get_movements(next_location)
                # Update path taken and current location
                self.path_taken.append(next_location)
                self.current_location = next_location
                self.heading_history.append(self.heading)
        
        else:
            next_location = self.best_path[self.best_path.index(self.current_location) - 1]
            rotation, movement = self.get_movements(next_location)
            self.current_location = next_location
        
        return rotation, movement