import progressbar
from textrepo.client import TextRepoClient


def default_progress_bar(max_value):
    widgets = [' [',
               progressbar.Timer(format='elapsed time: %(elapsed)s'),
               '] ',
               progressbar.Bar('*'),
               ' (',
               progressbar.ETA(),
               ') ',
               ]
    return progressbar.ProgressBar(max_value=max_value,
                                   widgets=widgets).start()


def trc_has_document_with_external_id(trc: TextRepoClient, external_id: str) -> bool:
    try:
        metadata = trc.find_document_metadata(external_id)
        return metadata is not None
    except Exception:
        return False
