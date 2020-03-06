import pdb
import os
import pandas as pd
import numpy as np
pd.options.mode.chained_assignment = None

class Projection:
    ''' Read and Store Fangraphs Projection files in instance of class Projection.

    Parameters
    ----------
    path_data : string [optional]
        Where the data is stored (before date)

    model : string [optional]
        Choose from ZiPS (default), Steamer, Fans

    year: int [optional]
        year of projections

    Returns
    -------
    Instance of Projection, which contains:
        Objects:
        - self.statline
        - self.hitters_rank
        - self.pitchers_rank
        - self.hitter_stats
        - self.pitchers_stats

        Functions:
        - precompute_statlines

    '''

    def __init__(self, model = 'ZiPS', year = 2020, path_data = "projections/",
                 ranking_method = 'Yahoo', ranking_file = False):
        self.statline = {}
        self.all_rank = {}
        self.hitters_rank = {}
        self.pitchers_rank= {}
        self.hitters_stats = pd.DataFrame()

        # Read in Batters by Position for Year and Position
        if ranking_method == 'Yahoo':
            ranking_file = 'Yahoo_Roto_Ranking_'+str(year)+'.xlsx'
        elif ranking_method == 'RotoGraphs':
            ranking_file = 'RotoGraphsPositionalRankings'+str(year)+'.xlsx'
        elif ranking_method == 'ESPN':
            ranking_file = 'ESPN_Roto_Ranking_Full_'+str(year)+'.xlsx'
        elif ranking_method == 'FantasyPros':
            ranking_file = 'FantasyPros_Roto_Ranking_'+str(year)+'.xlsx'
        #else:
        #    ranking_file = ranking_file

        # Use Rotographs
        rotographs_file = 'RotoGraphsPositionalRankings'+str(year)+'.xlsx'
        rls = pd.ExcelFile(os.path.join(path_data+str(year)+'/PositionalRankings/RotoGraphs/',rotographs_file))
        xls = pd.ExcelFile(os.path.join(path_data+str(year)+'/PositionalRankings/'+ranking_method+'/',ranking_file))
        self.all_rank = pd.read_excel(xls, skiprows = 0, names = ['Rank','PLAYER','EligiblePosition'], index_col = 'Rank')
        for irename in range(len(self.all_rank)):
            self.all_rank.iloc[irename]['PLAYER'] = simplify_name(self.all_rank.iloc[irename]['PLAYER'])

        #pdb.set_trace()
        # Loop through all files in path.
        for file in os.listdir(path_data+str(year)+'/'):
            # Skip files that don't end in a position.
            if file.startswith(model) & ~file.endswith('Hitters.csv') & ~file.endswith('Pitchers.csv') :
                #print(os.path.join(path_data+str(year)+'/', file))
                df = pd.read_csv(os.path.join(path_data+str(year)+'/', file), index_col = 'playerid')
                fn = str.split(file,'.')[0][-2:]
                if fn == '_C': fn = 'C'
                #print fn
                df['Position'] = fn
                df['Rank'] = 999
                if self.hitters_stats.empty:
                    self.hitters_stats = df
                else:
                    self.hitters_stats = pd.concat([self.hitters_stats, df])

                #Read in Rotographs Ranking Predictions

                if fn != 'DH':
                    kk = 1
                    self.hitters_rank[fn] = pd.read_excel(rls, fn, skiprows =0, usecols=['Rank','PLAYER'], index_col = 'Rank', names = ['Rank','PLAYER'])

                    #self.hitters_rank[fn]['Drafted'] = 0

                    for plr in self.hitters_rank[fn]['PLAYER']:
                        ind = self.hitters_stats['Name'] == plr
                        self.hitters_stats['Rank'][ind] = kk
                        kk += 1

        self.hitters_stats['1B'] = self.hitters_stats['H'] - self.hitters_stats['2B'] - self.hitters_stats['3B'] - self.hitters_stats['HR']

        # Read in Pitchers for Year and Position
        for file in os.listdir(path_data+str(year)+'/'):
            if file.startswith(model) & file.endswith('Pitchers.csv'):
                #print(os.path.join(path_data+str(year)+'/', file))
                self.pitchers_stats = pd.read_csv(os.path.join(path_data+str(year)+'/', file))
                self.pitchers_stats['Position'] = 'P'
                self.pitchers_stats['Rank'] = 999
        self.pitchers_stats['CG']  = 0
        self.pitchers_stats['SHO']  = 0
        self.pitchers_stats['SV']  = 0
        self.pitchers_stats['BSV']  = 0

        #Read in Rotographs Ranking Predictions
        pitcher_positions = ['SP','RP']
        for fn in pitcher_positions:
            k = 1
            self.pitchers_rank[fn] = pd.read_excel(rls, fn, skiprows =0, usecols=['Rank','PLAYER'], index_col = 'Rank', names = ['Rank','PLAYER'])
            #self.pitchers_rank[fn]['Drafted'] = 0
            for plr in self.pitchers_rank[fn]['PLAYER']:
                ind = self.pitchers_stats['Name'] == plr
                self.pitchers_stats['Position'][ind] = fn
                self.pitchers_stats['Rank'][ind] = k
                k += 1
                if fn == 'SP':
                    self.pitchers_stats['CG'][ind] = np.floor(self.pitchers_stats['IP'][ind] * 0.01 * (1./self.pitchers_stats['WHIP'][ind]))
                    self.pitchers_stats['SHO'][ind] = np.ceil(self.pitchers_stats['CG'][ind] *0.55)
                if fn == 'RP':
                    self.pitchers_stats['SV'][ind] = np.floor(self.pitchers_stats['IP'][ind] * 0.5 * (1./self.pitchers_stats['WHIP'][ind]))
                    self.pitchers_stats['BSV'][ind] = np.floor(self.pitchers_stats['IP'][ind] * 0.05 * (1./self.pitchers_stats['WHIP'][ind]))
def simplify_name(name_in):
    name_out = (((name_in.replace('ñ','n')).replace('í','i')).replace('é','e')).split(' Jr.')
    return name_out[0]
