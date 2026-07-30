from importlib.resources import files
from dicebear import Avatar, Style

_style = Style.from_json(
    files("dicebear_styles").joinpath("big-smile.json").read_text("utf-8")
)

def generate_avatar_svg(seed, options=None):
    base_options = {"seed":seed, "mouthVariant":[]}
    if options:
        base_options.update(options)
    avatar = Avatar(_style, base_options)
    return avatar.to_string()