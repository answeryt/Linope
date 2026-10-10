# -*- coding: utf-8 -*-
"""Extract text and images from the paper PDF for translation."""
import fitz
import os
import json

BASE = r'C:\Users\86182\Desktop\github-project\deepseek-harness-master'
PDF = os.path.join(BASE, 'paper_1510.08510.pdf')
OUT_DIR = os.path.join(BASE, 'paper_extract')
IMG_DIR = os.path.join(OUT_DIR, 'images')
os.makedirs(IMG_DIR, exist_ok=True)

doc = fitz.open(PDF)
summary = {'pages': len(doc), 'metadata': doc.metadata}

all_text = []
img_manifest = []
for i, page in enumerate(doc):
    text = page.get_text('text')
    all_text.append(f'===== PAGE {i+1} =====\n{text}')
    for j, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        pix = fitz.Pixmap(doc, xref)
        if pix.n - pix.alpha > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        name = f'p{i+1}_img{j}_x{xref}.png'
        path = os.path.join(IMG_DIR, name)
        pix.save(path)
        # image position on page
        rects = page.get_image_rects(xref)
        rect = rects[0] if rects else None
        img_manifest.append({
            'page': i + 1, 'xref': xref, 'file': name,
            'size': (pix.width, pix.height),
            'rect': [round(v, 1) for v in (rect.x0, rect.y0, rect.x1, rect.y1)] if rect else None,
        })
        pix = None

with open(os.path.join(OUT_DIR, 'text.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(all_text))
with open(os.path.join(OUT_DIR, 'images.json'), 'w', encoding='utf-8') as f:
    json.dump(img_manifest, f, ensure_ascii=False, indent=1)

print('pages:', summary['pages'])
print('images extracted:', len(img_manifest))
for m in img_manifest:
    print(m)
print('text chars:', sum(len(t) for t in all_text))
