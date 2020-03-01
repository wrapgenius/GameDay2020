import os
import copy
import numpy as np
import pandas as pd
pd.options.mode.chained_assignment = None

class Draft:

    def __init__(self, projections_object,
                 draft_position = 2,
                 number_teams = 12,
                 roster_spots = {'C':1,'1B':1,'2B':1, '3B':1,'SS':1,'OF':3,'UTIL':1,'SP':2,'RP':2,'P':3,'BN':5},
                 batter_stats  = ['AB','R','1B','2B', '3B','HR','RBI','SB','BB','AVG','OPS'],
                 pitcher_stats = ['IP','W', 'L','CG','SHO','SV','BB','SO','ERA','WHIP','BSV'] ):

        self.number_teams = number_teams
        self.number_rounds = sum(roster_spots.values())
        self.draft_position = draft_position - 1 # e.g., 1st pick is 0!
        self.player_projections = projections_object
        self.remaining_ranked_players = projections_object.all_rank
        self.roto_stats_batting = pd.DataFrame(columns =  batter_stats[1:])
        self.roto_stats_pitching = pd.DataFrame(columns =  pitcher_stats[1:])
        self.teams = {}
        # Eventually make this smarter, e.g.;
        # self.roster_spots{"fielders":{'C':1,'1B':1,'2B':1, '3B':1,'SS':1,'OF':3,'UTIL':1},
        #                   "pitchers":{'SP':2,'RP':2,'P':3}
        #                    "bench":{'BN':5}}
        self.fielders = ['C','1B','2B','3B','SS','OF','UTIL']
        self.pitchers = ['SP', 'RP', 'P']
        for i in np.arange(number_teams):
            roto_stats = {}
            roto_stats['batting_stats'] = pd.DataFrame(columns =  batter_stats)
            roto_stats['pitching_stats'] = pd.DataFrame(columns =  pitcher_stats)
            roto_stats['roster_spots'] = roster_spots.copy()
            roto_stats['roster'] = {}
            self.teams[i] = roto_stats

    # Find Resulting Standings
    def tabulate_roto(self, teams):
        # Determine which stats to include in roto scores
        batting_stat_names = self.roto_stats_batting.columns.values.tolist()
        pitching_stat_names = self.roto_stats_pitching.columns.values.tolist()

        # Estimate batting and pitching seperately and combine later
        roto_stats_batting = self.roto_stats_batting.copy()
        roto_stats_pitching = self.roto_stats_pitching.copy()

        # Estimate Statlines for each team and append to roto_stats_batting/pitching
        for iteam in np.arange(self.number_teams):
            raw_team_batting = teams[iteam]['batting_stats']
            raw_team_pitching = teams[iteam]['pitching_stats']
            roto_team_batting = raw_team_batting.sum()
            roto_team_pitching = raw_team_pitching.sum()

            # Weight Rate Stats by the number of AB or IP
            rate_stats = ['AVG','OPS','ERA','WHIP']
            for istats in batting_stat_names:
                if istats in rate_stats:
                    roto_team_batting[istats] = (raw_team_batting[istats]*raw_team_batting['AB']).sum()/raw_team_batting['AB'].sum()
            for istats in pitching_stat_names:
                if istats in rate_stats:
                    roto_team_pitching[istats] = (raw_team_pitching[istats]*raw_team_pitching['IP']).sum()/raw_team_pitching['IP'].sum()
            roto_stats_batting = roto_stats_batting.append(roto_team_batting[batting_stat_names],ignore_index = True)
            roto_stats_pitching = roto_stats_pitching.append(roto_team_pitching[pitching_stat_names],ignore_index = True)

        # Combine pitching and hitting into single DataFrame.
        roto_team_stats = pd.concat([roto_stats_batting, roto_stats_pitching], axis=1, sort=False)

        # Find Rank in ascending and descending order (suboptimal?)
        roto_standings_desc = pd.concat([roto_stats_batting.rank(ascending=False), roto_stats_pitching.rank(ascending=False).rename(columns={"BB": "BBP"})], axis=1, sort=False)
        roto_standings_ascn = pd.concat([roto_stats_batting.rank(), roto_stats_pitching.rank().rename(columns={"BB": "BBP"})], axis=1, sort=False)

        # Reverse rank of stats in which lower values are better.
        avg_stats = ['L','CS','BBP','ERA','WHIP','BSV']
        for avg_stat in avg_stats:
            if avg_stat in roto_standings_desc:
                roto_standings_ascn[avg_stat] = roto_standings_desc[avg_stat]
        roto_standings = roto_standings_ascn.sum(axis=1).sort_values(ascending=False)
        roto_placement = roto_standings.index.get_loc(self.draft_position) + 1 # standings starting from 1 (not 0)

        return roto_team_stats, roto_stats_batting, roto_stats_pitching, roto_standings, roto_placement, roto_standings_ascn

    def draft_into_teams(self, single_team, drafted_player, position, silent = False):
        # Put the drafted_player with specified position into the roster of single_team.

        if silent == False:
            print('Picked '+drafted_player.iloc[0].PLAYER+' for '+position)

        # Different Stats Entries for Pitchers and Batters
        if drafted_player.EligiblePosition.str.contains('P').bool() == True:
            idx_player = self.player_projections.pitchers_stats.Name.values == drafted_player.iloc[0].PLAYER
            statline = self.player_projections.pitchers_stats[idx_player][single_team['pitching_stats'].keys()]
            single_team['pitching_stats'] = single_team['pitching_stats'].append(statline[0:1])

        else:
            idx_player = self.player_projections.hitters_stats.Name.values == drafted_player.iloc[0].PLAYER
            statline = self.player_projections.hitters_stats[idx_player][single_team['batting_stats'].keys()]
            single_team['batting_stats'] = single_team['batting_stats'].append(statline[0:1])

        # Subtract position spot from roster_spots
        single_team['roster_spots'][position] -= 1

        # Add Player to single_team Roster
        if position in single_team['roster']:
            single_team['roster'][position] = [single_team['roster'][position], drafted_player.PLAYER.values[0:1]]
        else:
            single_team['roster'][position] = drafted_player.PLAYER.values[0:1]

        return single_team

    def get_optimal_position(self, positions_in, roster_spots):
        # In the event that player is eligible for more than one position, return the optimal position to fill

        # Split players eligible for more that one position, e.g., 1B/OF
        single_positions = positions_in.split('/')

        # Check Pitchers
        P = False
        if ('RP' in single_positions):
            P = True
            if (roster_spots['RP'] > 0):
                return  'RP'
        elif ('SP' in single_positions):
            P = True
            if (roster_spots['SP'] > 0):
                return  'SP'
        if P == True:
            if (roster_spots['P'] > 0):
                return  'P'
            elif (roster_spots['BN'] > 0):
                return 'BN'
            else:
                return 0

        # Check Hitters
        Util = False
        if ('C' in single_positions):
            Util = True
            if (roster_spots['C'] > 0):
                return  'C'
        elif ('2B' in single_positions):
            Util = True
            if (roster_spots['2B'] > 0):
                return  '2B'
        elif ('SS' in single_positions):
            Util = True
            if (roster_spots['SS'] > 0):
                return  'SS'
        elif ('OF' in single_positions):
            Util = True
            if (roster_spots['OF'] > 0):
                return  'OF'
        elif ('3B' in single_positions):
            Util = True
            if (roster_spots['3B'] > 0):
                return  '3B'
        elif ('1B' in single_positions):
            Util = True
            if (roster_spots['1B'] > 0):
                return  '1B'
        elif ('Util' in single_positions):
            Util = True
            if (roster_spots['UTIL'] > 0):
                return  'UTIL'
        if Util == True:
            if (roster_spots['UTIL'] > 0):
                return  'UTIL'
            elif (roster_spots['BN'] > 0):
                return 'BN'
            else:
                return 0
        else:
            return 0

    # Do the entire draft one round at a time
    def draft_all(self, naive_draft = False):
        for iround in np.arange(self.number_rounds):
            self.teams, self.remaining_ranked_players = self.draft_round(iround, self.teams, self.remaining_ranked_players, naive_draft = naive_draft)
        self.roto_team_stats,self.roto_stats_batting,self.roto_stats_pitching,self.roto_standings,self.roto_placement,self.roto_team_stats_rank = self.tabulate_roto(self.teams)

    # Draft each round one team at a time.  When reaching "draft_position", stop and to pseudo_drafts to figure out best choice.
    def draft_round(self, round_key, teams, df, naive_draft = False):

        # Reverse draft order every other round
        draft_order = np.arange(self.number_teams)
        if round_key % 2 == 1:
            draft_order = draft_order[::-1]

        # Makde deep copies so that search for best position does not write to master
        teams_copy = copy.deepcopy(teams)
        df_copy = copy.deepcopy(df)

        # Draft each round one team at a time
        for iteam in draft_order:

            # Defaults to search for best picks at draft_position.  Skips when naive_draft == True
            if naive_draft == False:
                # When team is draft_position, search for best pick.
                if iteam == self.draft_position:
                    best_pick, best_position = self.find_best_pick(iteam, teams_copy, df_copy, round_key)
                    teams_copy, df_copy = self.draft_next_best(iteam, teams_copy, df_copy, force_pick = best_pick, force_position = best_position)
                else:
                    teams_copy, df_copy = self.draft_next_best(iteam, teams, df_copy)
            else:
                teams_copy, df_copy = self.draft_next_best(iteam, teams_copy, df_copy)

        return teams_copy, df_copy

    def draft_remaining(self, teams_copy, df_copy, draft_round):

        # Draft all remaining players
        for iround in range(draft_round,self.number_rounds):

            draft_order = np.arange(self.number_teams)

            # Reverse draft order every other round
            if iround % 2 == 1:
                draft_order = draft_order[::-1]

            # For the very first round begin at beginning self.draft_position
            if iround == draft_round:
                if iround % 2 == 1:
                    starting_position = self.number_teams - self.draft_position;
                else:
                    starting_position = self.draft_position + 1;
                draft_order = draft_order[starting_position:]

            # Finish the draft by picking the next best player in an open position
            # However, if drafting first or last, every other round will be the last pick.
            # if starting_position < self.number_teams:
            if len(draft_order) > 0:
                for iteam in draft_order:
                    teams_copy, df_copy = self.draft_next_best(iteam, teams_copy, df_copy)

        return teams_copy, df_copy

    def find_best_pick(self, team_key, teams_copy, df_copy, round_key, search_depth = 1, silent = True):
        # find_best_pick returns iloc, the index (of df) of the optimal pick, and the position being filled

        # Determine which roster_spots are still unfilled
        unfilled_positions = [k for (k,v) in teams_copy[team_key]['roster_spots'].items() if v > 0]
        idx_eligible = []
        pos_eligible = []

        # Find index of best player at each remaining position
        for iunfilled in unfilled_positions:
            if iunfilled == 'UTIL':
                idx_position = [i for i, val in enumerate(df_copy.EligiblePosition.str.contains('|'.join(self.fielders))) if val]
            elif iunfilled == 'P':
                idx_position = [i for i, val in enumerate(df_copy.EligiblePosition.str.contains('|'.join(self.pitchers))) if val]
            elif iunfilled == 'BN':
                idx_position = [i for i, val in enumerate(df_copy.EligiblePosition.str.contains('|'.join(self.fielders+self.pitchers))) if val]
            else:
                idx_position = [i for i, val in enumerate(df_copy.EligiblePosition.str.contains(iunfilled)) if val]
            filled = False
            jdx = 0
            while filled == False:
                if idx_position[jdx] in idx_eligible:
                    jdx+=1
                else:
                    idx_eligible.append(idx_position[jdx])
                    pos_eligible.append(iunfilled)
                    #Increase search_depth (how?)
                    #idx_eligible.append((idx_position[jdx+i] for i in range(search_depth)))
                    #pos_eligible.append((iunfilled for i in range(search_depth)))
                    filled = True

        # Get rid of doubles (1B and OF is particularly prone)
        idx_eligible, idx_unique = np.unique(idx_eligible, return_index = True)
        pos_eligible = [pos_eligible[i] for i in idx_unique]
        #if silent == False:
        #    print('Picking from:')
        #    print(df_copy.iloc[idx_eligible])

        #################################
        # START OF LOOP TO FIND BEST PLAYER
        player_based_drafted_outcomes = {}
        player_based_drafted_teams = {}

        # Loop over eligible players, then finish the draft
        for iposition, icounter in zip(idx_eligible, range(len(idx_eligible))):

            # make a copy of teams to finish drafting
            teams_loop = copy.deepcopy(teams_copy)
            df_loop = copy.deepcopy(df_copy) #df_copy.copy()

            # Get iplayer before dropping
            iplayer = df_loop.iloc[iposition].PLAYER

            # Draft looping through idx_eligible
            df_loop,drafted_player=df_loop.drop(df_loop.iloc[iposition:iposition+1].index),df_loop.iloc[iposition:iposition+1]
            position = pos_eligible[icounter]

            teams_loop[team_key] = self.draft_into_teams(teams_loop[team_key], drafted_player, position, silent = True)

            # LOOP OVER WHOLE REST OF THE DRAFT HERE...
            teams_loop, df_loop = self.draft_remaining(teams_loop, df_loop, round_key)

            # Calculate the best pseudo-standings
            #pseudo_team_stats, pseudo_batting_stats, pseudo_pitching_stats, pseudo_standings, pseudo_placement = self.tabulate_roto(teams_loop)
            roto_stats = self.tabulate_roto(teams_loop)

            # Store the result.
            player_based_drafted_teams[iplayer] = teams_loop[self.draft_position]['roster']
            player_based_drafted_outcomes[iplayer] = [roto_stats[4],roto_stats[3][roto_stats[4]-1]]
            if silent == False:
                print('Stored Result for Pick '+str(icounter)+' '+iplayer+' '+pos_eligible[icounter]+' whose placing/score is '+str(player_based_drafted_outcomes[iplayer]))

        # End of Loop
        ranked_positions = ['C','2B','SS','OF','3B','1B','SP','RP','UTIL','P','BN']

        # Decide on best choice and return
        relative_ranking = [player_based_drafted_outcomes[i][0] for i in player_based_drafted_outcomes]
        relative_ranking_rank = np.argsort(relative_ranking)
        relative_scores = [player_based_drafted_outcomes[i][1] for i in player_based_drafted_outcomes]

        # If there is a tie for top relative_ranking, select by highest score, then optimal position
        n_max_ranking = sum(relative_ranking == np.min(relative_ranking))
        if n_max_ranking == 1:
            best_player = df_copy.iloc[idx_eligible[relative_ranking_rank[0]]:idx_eligible[relative_ranking_rank[0]]+1]
            best_pick_plus_one = idx_eligible[relative_ranking_rank[0]] + 1 # Avoid best_pick = 0
            best_position = pos_eligible[relative_ranking_rank[0]]
        else:
            # Of those tied for top rank, figure out had a highest score
            best_player_scores = [relative_scores[relative_ranking_rank[i]] for i in range(n_max_ranking)]
            best_players = [df_copy.iloc[idx_eligible[relative_ranking_rank[i]]] for i in range(n_max_ranking)]
            best_picks_plus_one = [idx_eligible[relative_ranking_rank[i]] + 1 for i in range(n_max_ranking)]
            best_player_positions = [pos_eligible[relative_ranking_rank[i]] for i in range(n_max_ranking)]
            idx_best_player_scores = np.argsort(best_player_scores)[::-1]

            # If still tied, take the optimal position (i.e., SS over OF)
            n_max_scores = sum(best_player_scores == np.max(best_player_scores))
            if n_max_scores == 1:
                best_player = df_copy.iloc[best_picks_plus_one[idx_best_player_scores[0]]-1:best_picks_plus_one[idx_best_player_scores[0]]-1+1]
                best_pick_plus_one = best_picks_plus_one[idx_best_player_scores[0]]
                best_position = best_player_positions[idx_best_player_scores[0]]
            else:
                best_player_positions = [pos_eligible[idx_best_player_scores[i]] for i in range(n_max_scores)]
                for irank in range(len(ranked_positions)):
                    if any(ranked_positions[irank] in s for s in best_player_positions):
                        idx_best = best_player_positions.index(ranked_positions[irank])
                        best_player = df_copy.iloc[best_picks_plus_one[idx_best_player_scores[idx_best]]-1:best_picks_plus_one[idx_best_player_scores[idx_best]]-1+1]
                        best_pick_plus_one = best_picks_plus_one[idx_best_player_scores[idx_best]]
                        best_position = ranked_positions[irank]
                        break

        # Need to not fill UTIL if other opening exist...
        if (best_position == 'UTIL'):
            alternative_positions = unfilled_positions
            player_positions = best_player.EligiblePosition.values[0].split('/')
            if any('P' in s for s in alternative_positions):
                if 'SP' in alternative_positions: alternative_positions.remove('SP')
                if 'RP' in alternative_positions: alternative_positions.remove('RP')
                if 'P' in alternative_positions: alternative_positions.remove('P')
            for altp in player_positions:
                if any(altp in s for s in alternative_positions):
                    best_position = altp
                    print('Swapping UTIL with '+ best_position)

        return best_pick_plus_one, best_position
        # END OF LOOP TO FIND BEST PLAYER
        #################################

    # Strategy is to take the best possible player, even if that means putting them in UTIL or BN (maybe BN should reconsidered...)
    def draft_next_best(self, team_key, teams, df, force_pick = False, force_position = False, silent = True):

        if (force_pick == False):
            pick_ok = False
            idf = 0
            while (pick_ok == False):
                df_copy = copy.deepcopy(df)
                pick_ok = True

                # Draft next in list.  Do this way (idf) so that if you don't take player, they are not removed for next picker
                df_copy,drafted_player=df_copy.drop(df_copy.iloc[idf:idf+1].index),df_copy.iloc[idf:idf+1]

                # Get eligible positions
                try:
                    eligible_positions = drafted_player.EligiblePosition.values[0]
                except:
                    pdb.set_trace()
                # Find best position opening.  Return 0 if no room
                position = self.get_optimal_position(eligible_positions, teams[team_key]['roster_spots'])

                # Update Rosters with drafted_player, Loop otherwise
                if position == 0:
                    unfilled_positions = [k for (k,v) in self.teams[team_key]['roster_spots'].items() if v > 0]
                    if silent == False:
                        print('Not Drafting '+eligible_positions+" "+drafted_player.PLAYER+' for '+ "/".join(unfilled_positions))
                    idf += 1
                    if len(unfilled_positions) > 0:
                        pick_ok = False
                    else:
                        pick_ok = True
                else:
                    if silent == False:
                        print('Team '+ str(team_key) +' Drafting '+drafted_player.iloc[0].PLAYER+' for '+position)
                    df = df_copy
                    pick_ok = True
                    teams[team_key] = self.draft_into_teams(teams[team_key], drafted_player,position, silent = True)

        else:

            pick_ok = True
            pick = force_pick - 1
            df,drafted_player=df.drop(df.iloc[pick:pick+1].index),df.iloc[pick:pick+1]
            eligible_positions = drafted_player.EligiblePosition.values[0]
            position = force_position

            teams[team_key] = self.draft_into_teams(teams[team_key], drafted_player, position, silent = True)
            #if silent == False:
            print('Team '+ str(team_key+1) +' picking '+drafted_player.iloc[0].PLAYER+' for '+position)

        return teams, df

    def draft_from_list_and_find_best_pick(self,search_depth = 1, path_list = 'Draft_Pick_Spreadsheets/", draft_pick_file = 'TestPicks.xlsx'):
        # Read in Excel Sheet and draft picks before moving on to finishing script

        xls = pd.ExcelFile(os.path.join(path_list,draft_pick_file))
        complete_player_list = pd.read_excel(xls, skiprows =0, names = ['Pick','PLAYER','EligiblePosition'], index_col = 'Pick')
        player_list = complete_player_list.loc[complete_player_list.index.dropna().values]

        teams_copy = copy.deepcopy(self.teams)
        df_copy = copy.deepcopy(self.remaining_ranked_players)

        for iround in np.arange(self.number_rounds):
            # Reverse draft order every other round
            draft_order = np.arange(self.number_teams)
            iter_team = 1
            if iround % 2 == 1:
                draft_order = draft_order[::-1]
                iter_team = -1

            for iteam in draft_order:
                #print('Drafting Team '+str(iteam+1))
                #while (len(player_list) > 0):
                # Find player matching df_copy by iloc
                idx_match = [i for i, x in enumerate(df_copy['PLAYER'].str.match(player_list.PLAYER.iloc[0])) if x]
                player_list,drafted_player=player_list.drop(player_list.iloc[0:1].index),player_list.iloc[0]
                #print(drafted_player['PLAYER'])
                #print(idx_match[0])
                best_position = self.get_optimal_position(drafted_player.EligiblePosition, teams_copy[iteam]['roster_spots'])
                #print(best_position)
                teams_copy, df_copy = self.draft_next_best(iteam, teams_copy, df_copy, force_pick = idx_match[0] + 1, force_position = best_position)
                if len(player_list) == 0:
                    break
            if len(player_list) == 0:
                break

        # Find best pick
        print('Finding Best Pick For Team '+str(iteam+1+iter_team))
        best_pick, best_position = self.find_best_pick(iteam+iter_team,copy.deepcopy(teams_copy),copy.deepcopy(df_copy),iround,silent=False,search_depth = 1)
        best_player_this_round = df_copy.iloc[best_pick-1].PLAYER
        teams_copy, df_copy = self.draft_next_best(iteam+iter_team, teams_copy, df_copy, force_pick = best_pick, force_position = best_position)

        # Finish the draft and Rank
        teams_copy, df_copy = self.draft_remaining(teams_copy, df_copy, iround)

        # Calculate the best pseudo-standings
        roto_stats = self.tabulate_roto(teams_copy)
        print('Best Pick is ' + best_player_this_round+ ' putting you in ' + str(roto_stats[4]) + ' place')

        # Return Player Name and Projected Roto Stats
        return best_player_this_round, roto_stats

    def filter_injured_list(self, path_list = os.environ['BBPATH']+"GameDay2020/Injured_List_Spreadsheets", injured_list_file = 'Injuries2020.xlsx'):
        # Read in Excel Sheet of Players to Exclude.  Should this be moved to Projection?  Yes.

        xls = pd.ExcelFile(os.path.join(path_list,injured_list_file))
        injured_list = pd.read_excel(xls, skiprows =0, names = ['PLAYER'], index_col = 'PLAYER')
