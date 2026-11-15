"""Screen-based video subtitle selection; independent of browser/site APIs."""
def resolve_selection(region, scope='subtitle', bottom_percent=30):
    """Interpret the user's declared selection exactly once."""
    if len(region) != 4 or region[2] < 40 or region[3] < 18:
        raise ValueError('Altyazı alanı en az 40×18 piksel olmalı.')
    if scope == 'subtitle':
        return tuple(region)
    if scope == 'video':
        return subtitle_band(region, bottom_percent)
    raise ValueError('Bilinmeyen alan seçimi türü.')


def subtitle_band(video_region, bottom_percent=30):
    if not isinstance(bottom_percent, int) or not 15 <= bottom_percent <= 50:
        raise ValueError('Altyazı tarama bandı %15–50 aralığında olmalı.')
    x, y, width, height = video_region
    if width < 40 or height < 40:
        raise ValueError('Video bölgesi çok küçük.')
    band_height = max(20, round(height * bottom_percent / 100))
    return x, y + height - band_height, width, band_height
