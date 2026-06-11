import logging
from pathlib import Path
from datetime import datetime


def setup_logger():
    log_dir = Path(".virtuoso/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"virtuoso_{datetime.now():%Y%m%d}.log"
    
    logger = logging.getLogger("virtuoso")
    logger.setLevel(logging.DEBUG)
    
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger
