"""Small readers for rendered pages and the stylesheet, shared by the front-end tests."""
import re
from html.parser import HTMLParser

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}

class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.children, self.bits = tag, dict(attrs), parent, [], []

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def find_all(self, tag=None, **attrs):
        return [n for n in self.walk() if n is not self and (tag is None or n.tag == tag)
                and all(n.attrs.get(k.replace("_", "-")) == v for k, v in attrs.items())]

    def has_class(self, name):
        return name in (self.attrs.get("class") or "").split()

    def inside(self, tag):
        node = self.parent
        while node is not None:
            if node.tag == tag:
                return True
            node = node.parent
        return False

    @property
    def text(self):
        return " ".join(" ".join(" ".join(n.bits) for n in self.walk()).split())

class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", [], None)
        self.at = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.at)
        self.at.children.append(node)
        if tag not in VOID:
            self.at = node

    def handle_startendtag(self, tag, attrs):
        self.at.children.append(Node(tag, attrs, self.at))

    def handle_endtag(self, tag):
        node = self.at
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self.at = node.parent

    def handle_data(self, data):
        self.at.bits.append(data)

def parse(html):
    builder = _Builder()
    builder.feed(html)
    return builder.root

def headings(root):
    return [int(n.tag[1]) for n in root.walk() if re.fullmatch(r"h[1-6]", n.tag)]

def css_rules(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out = []

    def block(text, context):
        i = 0
        while i < len(text):
            j = text.find("{", i)
            if j == -1:
                break
            head = text[i:j].strip()
            depth, k = 1, j + 1
            while depth and k < len(text):
                depth += {"{": 1, "}": -1}.get(text[k], 0)
                k += 1
            body = text[j + 1:k - 1]
            if head.startswith("@media"):
                block(body, head)
            elif not head.startswith("@"):
                decls = {}
                for part in body.split(";"):
                    prop, _, value = part.partition(":")
                    if value.strip():
                        decls[prop.strip()] = value.strip()
                for selector in head.split(","):
                    name = " ".join(selector.split())
                    out.append((f"{context} :: {name}" if context else name, decls))
            i = k

    block(css, "")
    return out

def declarations(css, selector):
    merged = {}
    for name, decls in css_rules(css):
        if name == selector:
            merged.update(decls)
    return merged

def luminance(colour):
    colour = colour.lstrip("#")
    if len(colour) == 3:
        colour = "".join(c * 2 for c in colour)
    channels = [int(colour[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)
