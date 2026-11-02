from clipshrinker.ui.trim_editor import fit_size, format_time


def test_fit_size_keeps_aspect_and_even():
    assert fit_size(1920, 1080, 640, 360) == (640, 360)
    w, h = fit_size(1080, 1920, 640, 360)
    assert h == 360 and w % 2 == 0 and w < 640
    assert fit_size(0, 0, 640, 360) == (640, 360)


def test_format_time():
    assert format_time(0) == "0:00"
    assert format_time(10) == "0:10"
    assert format_time(65.5) == "1:05.5"
    assert format_time(3.25) == "0:03.25"
    assert format_time(3725) == "1:02:05"
    assert format_time(12.01, precise=False) == "0:12"
