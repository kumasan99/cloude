import pandas as pd, numpy as np, re
pd.set_option('display.width',300); pd.set_option('display.max_colwidth',70)
L='fb119036-______20200331_20260827_________________/'
Y='688f9eb4-______20250827_20260827_________________/'

def load(p):
    df=pd.read_csv(p+'表データ.csv')
    df.columns=['id','title','pub','len','views','wt_h','subs','avd','impr','ctr']
    tot=df[df.id=='合計'].iloc[0]
    df=df[df.id!='合計'].copy()
    df['pub']=pd.to_datetime(df['pub'],format='%b %d, %Y',errors='coerce')
    df['avd_s']=df['avd'].apply(lambda x: sum(int(v)*60**i for i,v in enumerate(reversed(str(x).split(':')))) if isinstance(x,str) and ':' in str(x) else np.nan)
    df['len']=pd.to_numeric(df['len'],errors='coerce')
    df['ret']=df.avd_s/df['len']*100
    df['type']=np.where(df['len']<=180,'Short','Long')
    return df,tot

life,ltot=load(L)
yr,ytot=load(Y)
print('=== LIFETIME TOTAL ==='); print(ltot.to_dict())
print('=== LAST 365D TOTAL ==='); print(ytot.to_dict())
print('\n=== lifetime videos:',len(life),' 期間内に再生のあった動画数')
print(life.groupby('type').agg(n=('views','size'),views=('views','sum'),med=('views','median'),mean=('views','mean'),subs=('subs','sum'),ctr=('ctr','median'),ret=('ret','median')))
print('\n=== 直近365日 ===',len(yr))
print(yr.groupby('type').agg(n=('views','size'),views=('views','sum'),med=('views','median'),mean=('views','mean'),subs=('subs','sum'),ctr=('ctr','median'),ret=('ret','median')))

print('\n\n########## TOP20 lifetime (views) ##########')
print(life.sort_values('views',ascending=False).head(20)[['title','pub','len','type','views','subs','ctr','ret','impr']].to_string(index=False))
print('\n########## TOP20 lifetime by SUBS gained ##########')
print(life.sort_values('subs',ascending=False).head(20)[['title','pub','len','type','views','subs','ctr','ret']].to_string(index=False))

print('\n########## 月別: 投稿本数と累計再生（公開月ベース, lifetime表） ##########')
life['ym']=life.pub.dt.to_period('M')
m=life.groupby(['ym','type']).agg(n=('views','size'),views=('views','sum'),med=('views','median')).unstack(fill_value=0)
print(m.tail(30).to_string())
