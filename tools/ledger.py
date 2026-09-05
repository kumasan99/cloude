#!/usr/bin/env python3
"""司令塔の一台帳（docs/ledger/tasks.csv, messages.csv）を編集する小道具。
プログラムが「書く」、AIが「決める」。手で列をずらす事故を防ぐためだけの道具。

使い方（リポジトリ直下で）:
  python3 tools/ledger.py tasks list [--open]            # 一覧（--open で完了以外）
  python3 tools/ledger.py tasks add "件名" "次の一手" 担当 待ち先 期日 状態 出典
  python3 tools/ledger.py tasks upd T087 --next "…" --status "…" --owner … --wait … --due …
  python3 tools/ledger.py msgs list [--open]
  python3 tools/ledger.py msgs add from to "件名" 本文リンク 期限
  python3 tools/ledger.py msgs ack  M011
  python3 tools/ledger.py msgs done M011
  python3 tools/ledger.py export  # Drive投入用CSVを scratchpad に出す（次の一手は140字で切る）
日付は JST の今日を自動で入れる。列の並びは変えない。
"""
import csv, sys, os, datetime, argparse
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T=os.path.join(ROOT,'docs/ledger/tasks.csv'); M=os.path.join(ROOT,'docs/ledger/messages.csv')
JST=datetime.timezone(datetime.timedelta(hours=9))
def now(): return datetime.datetime.now(JST)
def today(): n=now(); return f'{n.year}-{n.month}-{n.day}'
def stamp(): return now().strftime('%Y-%m-%d %H:%M')
def load(p):
    with open(p,encoding='utf-8',newline='') as f: return list(csv.reader(f))
def save(p,rows):
    with open(p,'w',encoding='utf-8',newline='') as f: csv.writer(f,lineterminator='\n').writerows(rows)
def nextid(rows,prefix):
    n=max([int(r[0][1:]) for r in rows[1:] if r and r[0].startswith(prefix)]+[0]); return f'{prefix}{n+1:03d}'
def main(a):
    if not a: print(__doc__); return
    if a[0]=='export':
        sp=os.environ.get('SCRATCHPAD','.')
        rows=load(T)
        for r in rows[1:]:
            t=r[2]; k=t.find('。全文は'); 
            if len(t)>140: r[2]=t[:140]+f'…（全文は{r[8]}）'
        save(os.path.join(sp,'export_tasks.csv'),rows); save(os.path.join(sp,'export_messages.csv'),load(M)); print('exported to',sp); return
    kind,cmd=a[0],a[1]; p=T if kind=='tasks' else M; rows=load(p)
    if cmd=='list':
        for r in rows[1:]:
            if '--open' in a and (r[6] in ('完了','done') or r[6].startswith('完了')): continue
            print(' | '.join([r[0],r[1] if kind=='tasks' else r[4],r[6],r[5] if kind=='tasks' else r[7]]))
    elif cmd=='add' and kind=='tasks':
        件名,次,担当,待ち,期日,状態,出典=(a[2:]+['']*7)[:7]
        rows.append([nextid(rows,'T'),件名,次,担当,待ち,期日,状態,today(),出典 or '司令塔']); save(p,rows); print(rows[-1][0])
    elif cmd=='add' and kind=='msgs':
        frm,to,件名,link,期限=(a[2:]+['']*5)[:5]
        rows.append([nextid(rows,'M'),stamp(),frm,to,件名,link,'open',期限,'','']); save(p,rows); print(rows[-1][0])
    elif cmd=='upd' and kind=='tasks':
        ap=argparse.ArgumentParser(); ap.add_argument('id'); ap.add_argument('--next'); ap.add_argument('--status'); ap.add_argument('--owner'); ap.add_argument('--wait'); ap.add_argument('--due')
        o=ap.parse_args(a[2:])
        for r in rows[1:]:
            if r[0]==o.id:
                if o.next: r[2]=o.next
                if o.owner: r[3]=o.owner
                if o.wait: r[4]=o.wait
                if o.due: r[5]=o.due
                if o.status: r[6]=o.status
                r[7]=today(); save(p,rows); print('updated',o.id); return
        print('not found',o.id); sys.exit(1)
    elif cmd in ('ack','done') and kind=='msgs':
        for r in rows[1:]:
            if r[0]==a[2]:
                r[6]=cmd; r[8 if cmd=='ack' else 9]=stamp(); save(p,rows); print(cmd,a[2]); return
        print('not found',a[2]); sys.exit(1)
    else: print(__doc__); sys.exit(1)
if __name__=='__main__': main(sys.argv[1:])
