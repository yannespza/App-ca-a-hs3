"""Versões leves das imagens do jogo (mapa em JPEG, ícones recortados e menores), guardadas numa pasta de cache.
O mapa exportado pelo jogo tem ~22 MB (PNG 4096x4096): no celular isso demorava muito para abrir."""
import os
import threading

try:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
except Exception:          # sem Pillow: o app usa as imagens originais
    Image = None

_trava = threading.Lock()


def disponivel():
    return Image is not None


def _destino(cache_dir, origem, sufixo):
    os.makedirs(cache_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(origem))[0]
    marca = int(os.path.getmtime(origem))
    return os.path.join(cache_dir, f"{base}_{marca}_{sufixo}")


def mapa_jpeg(origem, cache_dir, lado=2048, qualidade=82):
    """PNG do mapa -> JPEG do tamanho pedido (feito uma vez e guardado)."""
    if Image is None or not os.path.isfile(origem):
        return None
    lado = max(512, min(4096, int(lado)))
    dest = _destino(cache_dir, origem, f"{lado}.jpg")
    if os.path.isfile(dest):
        return dest
    with _trava:
        if os.path.isfile(dest):
            return dest
        with Image.open(origem) as im:
            im = im.convert("RGB")
            if im.width != lado:
                im = im.resize((lado, lado), Image.LANCZOS)
            tmp = dest + ".tmp"
            im.save(tmp, "JPEG", quality=qualidade, optimize=True, progressive=True)
            os.replace(tmp, dest)
        _limpar_antigos(cache_dir, os.path.splitext(os.path.basename(origem))[0], dest)
    return dest


def icone(origem, cache_dir, lado=220):
    """Ícone do jogo sem a borda transparente (armas ocupam só uma faixa do quadrado) e menor."""
    if Image is None or not os.path.isfile(origem):
        return None
    dest = _destino(cache_dir, origem, f"p{lado}.png")
    if os.path.isfile(dest):
        return dest
    with Image.open(origem) as im:
        im = im.convert("RGBA")
        caixa = im.getchannel("A").point(lambda a: 255 if a > 12 else 0).getbbox()
        if caixa:
            im = im.crop(caixa)
        im.thumbnail((lado, lado), Image.LANCZOS)
        tmp = dest + ".tmp"
        im.save(tmp, "PNG", optimize=True)
        os.replace(tmp, dest)
    return dest


def _limpar_antigos(cache_dir, base, manter):
    """Apaga versões velhas do mesmo mapa (o jogo exporta de novo quando muda)."""
    for n in os.listdir(cache_dir):
        p = os.path.join(cache_dir, n)
        if n.startswith(base + "_") and p != manter and not n.endswith((".jpg.tmp",)) and n.split("_")[-1] == os.path.basename(manter).split("_")[-1]:
            try:
                os.remove(p)
            except OSError:
                pass
