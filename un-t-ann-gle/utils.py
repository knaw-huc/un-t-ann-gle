import progressbar


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
