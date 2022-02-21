import re
import pandas as pd
import fuzzywuzzy
from fuzzywuzzy import process
import plotly.graph_objects as go
#from plotly.subplots import make_subplots


##################### FUNÇÕES USADAS NA ETAPA S1 - PROCESSAMENTO E TRATAMENTO DOS DADOS

# informações sobre tipo de features, contagem de valores, valores únicos e valores nulos ...
def df_info(df):
    """
    Função para exibição de informações relativas ao dataframe <df>:
    - column type
    - count values
    - unique values
    - null values
    - null values (%)
    """

    info=pd.DataFrame(df.dtypes).T.rename(index={0:'column type'})
    info=info.append(pd.DataFrame(df.count()).T.rename(index={0:'count values'}))
    info=info.append(pd.DataFrame(df.nunique()).T.rename(index={0:'unique values'}))
    info=info.append(pd.DataFrame(df.isnull().sum()).T.rename(index={0:'null values'}))
    info=info.append(pd.DataFrame(df.isnull().sum()/df.shape[0]*100).T.rename(index={0:'null values (%)'}))
    return info

def mark_invalid_plate(df, column):
    """
    Esta função retorna o índice dos registros em que as placas são inválidas considerando os formatos abaixo. 

    df - dataframe em análise.
    column - coluna com dado da placa.

    No final, cada linha será tratada com base neste índice e parâmetro <column>.
    -PLACA_CAVALO-haverá remoção do respectivo registro;
    -PLACA_CARRETA - será atribuído valor 'ERROR', mantendo o registro.

    Formato placas:
    ABC1234 BR antiga = UR atual
    ABC123  PY antiga = AR
    ABC123  AR antiga = PY
    
    <MERCOSUL>
    ABCD123 PY
    ABC1A23 BR
    AB123CD AR
    *ABC1234 UR = BR
    
    VALIDAR PLACA CONFORME O PAÍS - 
    #pat_obj = re.compile('^[A-Z]{2}[0-9]{3}[A-Z]{2}$') # 'AB123CD'
    #pat_obj = re.compile('^[A-Z]{3}[0-9]{4}$') # 'ABC1234'
    #pat_obj = re.compile('^[A-Z]{3}[0-9]{3}$') # 'ABC123'
    #pat_obj = re.compile('^[A-Z]{3}\d\D[0-9]{2}$') # 'ABC1A23'
    #pat_obj = re.compile('^[A-Z]{4}[0-9]{3}$') # 'ABCD123'
    """
    
    #regex para cada placa por país
    BR = '(^[A-Z]{3}[0-9]{4}$)|(^[A-Z]{3}\d\D[0-9]{2}$)' 
    AR = '(^[A-Z]{2}[0-9]{3}[A-Z]{2}$)'
    PY = '(^[A-Z]{3}[0-9]{3}$)|(^[A-Z]{4}[0-9]{3}$)'

    list_invalid = [] #lista de retorno da função - com os índices.
    
    for index, row in df.iterrows():
        flag = False     #será True quando a placa for inválida
        plate = row[column]
        ind = index

        #only PLACA_CARRETA, if = NO_DATA or TRUCK or ERROR, continue
        if (plate in ['NO_DATA','TRUCK','ERROR']):
            continue

        #regular expression to check the plate format
        plate_obj = re.compile(BR + '|' + AR + '|' + PY)
        plate_match = plate_obj.match(plate)
                        
        if not(plate_match): flag = True  
        
        if flag:
            list_invalid.append(index)
            
    return list_invalid

def check_search(df,string,column):
    """
    Função usada para verificar/ajustar o score de cada match em <replace_matches> 

    df      - dataframe para verificação.
    string  - palavra usada para pesquisa e cálculo do score aplicada à coluna <column>
    column  - coluna na qual será verificada a string <string>
    """

    search = string
    col = df[column].unique()

    # classifica por ordem alfabética
    col.sort()

    # obtém os mais próximos que combinam com <list_check...>
    matches = fuzzywuzzy.process.extract(search, col, limit=2000,
                                     scorer=fuzzywuzzy.fuzz.token_sort_ratio)
    # exibe matches
#    print('TOTAL MATCHES:{} \n\nMATCHES:'.format(len(matches)))
    return matches

def replace_matches(df, df_temp, column, string_to_match, string_country, min_ratio):
    """
    Função para atribuir à coluna <ORIGEM_PAIS> ou <DESTINO_PAIS> o código do país.
    cujo match com a string fornecida estão acima do valor passado para <min_ratio>
    
    df              - dataframe no qual haverá atribuição do código do país.
    df_temp         - dataframe usado temporariamente para que a execução do código seja mais rápida.
    column          - coluna com os dados sobre os quais será aplicada a pesquisa de <string_to_match> 
    string_to_match - palavra usada para pesquisa e cálculo do score aplicada à coluna <column>
    string_country  - código de duas letras referente ao país. Ex: BR, PY, AR, UR
    min_ratio       - valor mínimo do score a partir do qual será feita a seleção dos melhores matches.

    """

    # obtém uma lista de strings únicas na coluna desejada
    strings = df_temp[column].unique()
    
    # obtém os matches (tuplas - strings, percentual) conforme <string_to_match>
    matches = fuzzywuzzy.process.extract(string_to_match, strings, 
                                         limit=2000, scorer=fuzzywuzzy.fuzz.token_sort_ratio)

    # apenas obtém os matches que forem maiores ou iguais a <min_ratio>
    close_matches = [matches[0] for matches in matches if matches[1] >= min_ratio]

    # bool - obtém os registros cujos valores estão em <close_matches>
    rows_with_matches = df_temp[column].isin(close_matches)

    #armazena os índices dos registros com match == True
    for index,val in rows_with_matches.iteritems():
        if rows_with_matches[index]:
            # armazena no dataframe principal na <column_PAIS> o valor em <string_country> (país de origem/destino)
            df[column+'_PAIS'][df.index == index] = string_country
            #exclui registro usado para armazenar país, tornando o dataframe menor e mais rápida a execução 
            df_temp.drop(index = index, inplace=True, axis=0)
    

def show_days_month(df,column,list_month):
    """
    Exibe num dataframe <df_return> para cada mês o número de dias únicos (Ex:7: 31, 8: 31, 9: 30, 10: 27 - se tiver faltando 3 dias)
    Permite verificar se ficou faltando coletar algum dia do mês ou se realmente não existe determinado dia em <column> no mês específico.

    df          - dataframe de verificação dos dias do mês. 
    column      - coluna de datas onde será feita a verificação. Deve ser do tipo <datetime>
    list_month  - lista contendo os meses (inteiro de 1 a 12)

    Exemplo: exibição referente ao dataframe <df>, na coluna <column>, nos meses em <list_month>:
    show_days_month(mic,'DATA_PASSAGEM',[7,8,9,10])
    """

    t_dias = []
    n_dias = []
    
    for m in list_month:
        #último dia do mês <m>
        last_day_month = df[df[column].dt.month == m][column].min().date()
        last_day_month = pd.Period(last_day_month, freq='H').days_in_month

        #range de todos os dias de 1 até o fim do mês <m>
        all_days = range(1,last_day_month+1)

        #todos os dias encontrados no mês <m> no dataset <df>
        mdays = sorted(df[df[column].dt.month == m][column].dt.day.unique())
        
        #dias ausentes no mês <m> no dataset <df>
        not_days = [d for d in all_days if d not in mdays]

        #total de dias únicos encontrados em <df> no mês <m>    
        t_dias.append(len(mdays))
        #dias ausentes no mês <m> no dataset <df>    
        n_dias.append(not_days)

    df_return = pd.DataFrame({
        "MES": list_month,
        "DIAS": t_dias,
        "DIAS FALTANTES": n_dias
    }).set_index('MES')
    
    return df_return 
        
def char_remove(df,column):
    """
    Verifica se há em column caracter especial ou indevido.
    
    df - dataframe a ser executada a verificação
    column - coluna que será verificada a ocorrência de caracter especial ou indevido
    """
    count = df[column][df[column].str.contains('[''-\?\*\+\$\.\)\(\' !@%&_"\"/:;,"´~]')].count()

    if count > 0:
        #exclui os caracteres indevidos
        df[column] = df[column].str.replace(r'[''-\?\*\+\$\.\)\(\' !@%&_"\"/:;,"´~]',"",regex=True)
        

#S1_1
def search_idx_plates(list_plates, df_check,col_check):
    """
    Função que retorna os índices dos registros em <df_check> cujas placas estiverem em <list_plates>.
    
    list_plates - lista com as placas de interesse
    df_check - dataframe com as placas a serem pesquisadas. Deve-se observar que os registros deste dataframe serão removidos para otimizar a execução, logo deve-se enviar uma cópia do dataframe e não o original.
    col_check - coluna a ser verificada referente à placa em< df_check>

    """
    idx_found, search_idx_plates = [],[]
    flag = False
    for l_plate in list_plates:
        idx = df_check[df_check[col_check] == l_plate].index        

        if len(idx) > 0:
            idx_found.append(idx)
            df_check.drop(index = idx, inplace=True,axis=0)
            flag = True
              
    if flag:
        for ind in idx_found:
            for i in ind:
                search_idx_plates.append(i)

    return search_idx_plates

#S1_2 Anonimizacao e S2
def mark_plate_origem(df):
    """
    Esta função registra em feature booleana se a placa é nacional (brasileira) - PLACA_BR = True
    
    df - dataframe em análise.

    Formato placas:
    ABC1234 BR antiga = UR atual
    ABC123  PY antiga = AR
    ABC123  AR antiga = PY
        
    VALIDAR PLACA CONFORME O PAÍS - 
    #pat_obj = re.compile('^[A-Z]{3}[0-9]{4}$') # 'ABC1234'
    #pat_obj = re.compile('^[A-Z]{3}\d\D[0-9]{2}$') # 'ABC1A23'
    """
    
    #regex BR
    BR = '(^[A-Z]{3}[0-9]{4}$)|(^[A-Z]{3}\d\D[0-9]{2}$)' 

    for index, row in df.iterrows():
        placa = row['PLACA']
    
        #expressão regular para verificar o formato da placa
        obj = re.compile(BR)
        match_placa = obj.match(placa)
                        
        if (match_placa): 
            df['PLACA_BR'][df.index == index] =  True
            
            
def plot_grafico1(len_plot, len_base,x_title, x_tit_plot):
    """
    Exibe gráfico em barras com base nos valores dos parâmetros:
    
    len_plot    - tamanho do que se deseja plotar - numa lista
    len_base    - tamanho total da base, usado para cálculo relativo dos percentuais
    x_title     - título do gráfico
    x_tit_plot  - usado para identificação na parte inferior da barra - um para cada item de <len_plot>

    plot_grafico1([30,45,30,40,50],len_base=100,x_title='MIC',x_tit_plot=['bar1','bar2','bar3','bar4','bar5'])    
    """

    if len(len_plot) == 1:
        len_plot.append(len_base-len_plot[0])
   
    name = f'{(len_plot[0]/len_base*100):.2f}%'
    graf1 = go.Figure(data = go.Bar(x=[x_tit_plot[0]], y =[len_plot[0]], name=name))
    
    for i in range(len(len_plot)):
        if i > 0:
            name = f'{(len_plot[i]/len_base*100):.2f}%'
            graf1.add_bar(x=[x_tit_plot[i]], y =[len_plot[i]], name=name)

    graf1.layout.title=x_title+': '+str(len_base)
    graf1.update_layout(barmode='relative', bargap=0.07, width=300, height=300 )
    graf1.show()