OCR Pipeline
============

Multi-engine OCR with VLM merge for documents.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   Quick Start <self>
   modules
   api

Quick Start
-----------

Install from PyPI or source:

.. code-block:: bash

   pip install ocr-pipeline

Run OCR on a PDF:

.. code-block:: bash

   ocr-pipeline run --input document.pdf --output-dir ./output

Input Formats
-------------

The pipeline accepts 30+ document formats including PDF, EPUB, DOCX,
images (PNG/JPEG/TIFF), plain text, HTML, and more.

Output Formats
--------------

* Markdown (default)
* JSON (structured with blocks and metadata)
* hOCR (XHTML with CSS classes for OCR results)
* ALTO XML v4.4 (structured with bounding boxes)

Configuration
-------------

See ``config.example.yaml`` for all available options.  Create a local
``config.yaml`` to override defaults:

.. code-block:: yaml

   engines:
     - tesseract
     - surya2
   output_formats:
     - markdown
     - hocr

API Reference
-------------

See the :doc:`api` page for the full class reference.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
