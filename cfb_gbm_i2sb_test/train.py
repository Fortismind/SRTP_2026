import argparse
from cfb.training import train

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default='configs/short.json');p.add_argument('--kind',choices=['i2sb','regression'],default='i2sb');p.add_argument('--run',default='i2sb_short');p.add_argument('--resume')
    a=p.parse_args();train(a.config,a.kind,a.run,a.resume)
