import fitz
import pymupdf4llm

doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 50), "Hello world")
# add a small rectangle as a drawing
page.draw_rect(fitz.Rect(100, 100, 200, 200), color=(1, 0, 0), fill=(1, 0, 0))

chunks = pymupdf4llm.to_markdown(doc, page_chunks=True)
print("Default:", chunks[0]["text"])

chunks_img = pymupdf4llm.to_markdown(doc, page_chunks=True, write_images=True)
print("With images:", chunks_img[0]["text"])
