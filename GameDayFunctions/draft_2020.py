import pandas as pd
pd.options.mode.chained_assignment = None
import numpy as np

class Draft:

    def __init__(self, projections_object,
                 draft_position = 6,
                 number_teams = 12,
                 roster_spots = {'C':1,'1B':1,'2B':1, '3B':1,'SS':1,'OF':3,'UTIL':1,'SP':2,'RP':2,'P':3,'BN':5},
                 batter_stats  = ['AB','R','1B','2B', '3B','HR','RBI','SB','BB','AVG','OPS'],
                 pitcher_stats = ['IP','W', 'L','CG','SHO','SV','BB','SO','ERA','WHIP','BSV'] ):

        self.number_rounds = sum(roster_spots.values())
        self.draft_position = draft_position
        self.player_projections = projections_object
        self.remaining_ranked_players = projections_object.all_rank
        #self.roto_standings = []
        self.roto_stats_batting = pd.DataFrame(columns =  batter_stats[1:])
        self.roto_stats_pitching = pd.DataFrame(columns =  pitcher_stats[1:])
        self.teams = {}
        for i in np.arange(number_teams):
            roto_stats = {}
            roto_stats['batting_stats'] = pd.DataFrame(columns =  batter_stats)
            roto_stats['pitching_stats'] = pd.DataFrame(columns =  pitcher_stats)
            roto_stats['roster_spots'] = roster_spots.copy()
            roto_stats['roster'] = {}
            self.teams[i] = roto_stats

    # Do the entire draft one round at a time
    def draft_all(self):
        for iround in np.arange(self.number_rounds):
            self.draft_round(iround)
        self.tabulate_roto()

    # Do each round of the draft one team at a time
    def draft_round(self, round_key):
        # Reverse draft order every other round
        draft_order = np.arange(len(self.teams))
        if round_key % 2 == 1:
            draft_order = draft_order[::-1]
        for iteam in draft_order:
            self.draft_pick(iteam)

    # Define logic for round selection
    def draft_pick(self,team_key):
        pick_ok = False
        df = self.remaining_ranked_players
        while pick_ok == False:
            pick_ok = True

            # Figure out what positions are still unfilled.
            unfilled_positions = [k for (k,v) in self.teams[team_key]['roster_spots'].items() if v > 0]
            ups = '|'.join(unfilled_positions)
            #print(ups)

            # If the first value is not eligible, then need to decide if can be UTIL or BN
            idx_eligible = [i for i, val in enumerate(df.EligiblePosition.str.contains(ups)) if val]

            if len(idx_eligible) == 0 or idx_eligible[0] != 0:
                # Check if there are UTIL positions left
                df,drafted_player=df.drop(df.iloc[0:1].index),df.iloc[0:1]
                eligible_positions = drafted_player.EligiblePosition.values[0]
                if drafted_player.EligiblePosition.str.contains('P').bool() == True:
                    if self.teams[team_key]['roster_spots']['P'] > 0:
                        position = 'P'
                    elif self.teams[team_key]['roster_spots']['BN'] > 0:
                        position = 'BN'
                    else:
                        position = 'No Roster Spots Left'
                        pick_ok = False
                else:
                    if self.teams[team_key]['roster_spots']['UTIL'] > 0:
                        position = 'UTIL'
                    elif self.teams[team_key]['roster_spots']['BN'] > 0:
                        position = 'BN'
                    else:
                        position = 'No Roster Spots Left'
                        pick_ok = False

                #print(self.teams[team_key]['roster_spots'])
                #print('Considering '+drafted_player.PLAYER+' for '+position)
            else:
                pick = idx_eligible[0]
                df,drafted_player=df.drop(df.iloc[pick:pick+1].index),df.iloc[pick:pick+1]
                eligible_positions = drafted_player.EligiblePosition.values[0]

                # For those eligible for multiple positions, split them up and pick one
                tf_position = [p in eligible_positions for p in unfilled_positions]
                idx_position = [i for i, val in enumerate(tf_position) if val]
                position = unfilled_positions[idx_position[0]]

            if pick_ok == True:
                # Check if Position is a Pitcher or Batter
                if drafted_player.EligiblePosition.str.contains('P').bool() == True:
                    idx_player = self.player_projections.pitchers_stats.Name.values == drafted_player.iloc[0].PLAYER
                    statline = self.player_projections.pitchers_stats[idx_player][self.teams[team_key]['pitching_stats'].keys()]
                    self.teams[team_key]['pitching_stats'] = self.teams[team_key]['pitching_stats'].append(statline)

                else:
                    idx_player = self.player_projections.hitters_stats.Name.values == drafted_player.iloc[0].PLAYER
                    statline = self.player_projections.hitters_stats[idx_player][self.teams[team_key]['batting_stats'].keys()]
                    self.teams[team_key]['batting_stats'] = self.teams[team_key]['batting_stats'].append(statline)

                #remove player from self.remaining_ranked_players
                self.remaining_ranked_players = df

                # Eliminate one roster position
                self.teams[team_key]['roster_spots'][position] -= 1
                if position in self.teams[team_key]['roster']:
                    self.teams[team_key]['roster'][position] = [self.teams[team_key]['roster'][position], drafted_player.PLAYER.values[0]]
                else:
                    self.teams[team_key]['roster'][position] = drafted_player.PLAYER.values[0]
                #print('Team '+ str(team_key) +' Drafting '+drafted_player.PLAYER+' for '+position)
            #else:
            #    print('Not Drafting '+drafted_player.PLAYER)
            #    print(ups)
            #pdb.set_trace()

    def tabulate_roto(self):
        for iteam in np.arange(len(self.teams)):
            raw_team_batting = self.teams[iteam]['batting_stats']
            raw_team_pitching = self.teams[iteam]['pitching_stats']
            roto_team_batting = raw_team_batting.mean()
            roto_team_pitching = raw_team_pitching.mean()
            if 'AVG' in raw_team_batting:
                roto_team_batting['AVG'] = (raw_team_batting['AVG']*raw_team_batting['AB']).sum()/raw_team_batting['AB'].sum()
            if 'OPS' in raw_team_batting:
                roto_team_batting['OPS'] = (raw_team_batting['OPS']*raw_team_batting['AB']).sum()/raw_team_batting['AB'].sum()
            if 'ERA' in raw_team_pitching:
                roto_team_batting['ERA'] = (raw_team_pitching['ERA']*raw_team_pitching['IP']).sum()/raw_team_pitching['IP'].sum()
            if 'WHIP' in raw_team_pitching:
                roto_team_batting['WHIP'] = (raw_team_pitching['WHIP']*raw_team_pitching['IP']).sum()/raw_team_pitching['IP'].sum()
            batting_stat_names = self.roto_stats_batting.columns.values.tolist()
            pitching_stat_names = self.roto_stats_pitching.columns.values.tolist()
            self.roto_stats_batting = self.roto_stats_batting.append(roto_team_batting[batting_stat_names],ignore_index = True)
            self.roto_stats_pitching = self.roto_stats_pitching.append(roto_team_pitching[pitching_stat_names],ignore_index = True)

        self.roto_team_stats = pd.concat([self.roto_stats_batting, self.roto_stats_pitching], axis=1, sort=False)
        roto_standings_avgs = pd.concat([self.roto_stats_batting.rank(ascending=False), self.roto_stats_pitching.rank(ascending=False).rename(columns={"BB": "BBP"})], axis=1, sort=False)
        roto_standings_cnts = pd.concat([self.roto_stats_batting.rank(), self.roto_stats_pitching.rank().rename(columns={"BB": "BBP"})], axis=1, sort=False)
        avg_stats = ['CS','BBP','ERA','WHIP','BSV']
        for avg_stat in avg_stats:
            if avg_stat in roto_standings_avgs:
                roto_standings_cnts[avg_stat] = roto_standings_avgs[avg_stat]
        self.roto_standings = roto_standings_cnts.sum(axis=1).sort_values(ascending=False)
        self.roto_placement = self.roto_standings.index.get_loc(self.draft_position)
        #pdb.set_trace()
