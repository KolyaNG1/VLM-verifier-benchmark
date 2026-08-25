---
few_shot_examples:
  - image: nikolay_ai_360_annotation/examples/dku_reference.png
    annotation: nikolay_ai_360_annotation/examples/dku_reference.txt
---

# Scientific-figure annotation task

Write one precise, self-contained description of the supplied scientific figure in English.

The description will be checked against the image by a literal text-to-image
verifier. It is therefore essential to name every visible, meaningful entity and
every relationship, rather than giving only a high-level summary.

Describe every visually meaningful entity that such a verifier would need:

1. The overall layout: panels, their order, and the location of major regions.
2. Every image, plot, diagram block, legend, table, icon, label, axis, and important numeric or textual annotation.
3. Directed relationships, especially arrows: state the source, destination, direction, and visible label or operation.
4. Spatial relationships such as above, below, left of, right of, inside, connected to, or aligned with.
5. The data flow or conceptual flow represented by the diagram, in a natural reading order.

For arrows, do not merely say that two elements are connected. Explicitly state
which element the arrow starts from and which element it points to. Preserve
visible direction, ordering, nesting, colours when they distinguish components,
and exact readable labels, including numbers and probabilities.

## Example of the required level of detail

The following is a style example for a different diagram. It illustrates the
required coverage; its entities must never be copied into the target answer.

1. At the bottom, a photograph of a child sitting in a car enters the blue
   **Backbone CNN / Transformers** block through an upward arrow. A green token
   list to the right of this input image contains **bottle**, **car**, and
   **person**.
2. An upward arrow leads from **Backbone CNN / Transformers** to the horizontal
   blue **Feature Map / Embeddings** block. The feature map sends one branch up
   into the **Implicit Support-Concepts (S)** strip inside the pale-green,
   dashed **Differentiable Knowledge Unit (DKU)** boundary, and another branch
   upward to the oval variable **z**.
3. Inside the DKU, the support-concepts strip contains a row of heat-map images.
   Its output and the teal **IF... THEN... Rules (R)** scroll are inputs to the
   purple **Fuzzy Inference** block; the rule-to-inference connection is dashed.
4. A teal **Initial Classifier p(yₖ|z)** receives **z** and is accompanied by a
   class-probability list in which **aeroplane (0.13)** and **chair (0.28)** are
   marked. Fuzzy inference sends an arrow to the upper **z-hat** oval.
5. The upper **z-hat** flows through the blue **σ(z-hat) Sigmoid** block to a
   reconstructed child photograph. A second probability list at the upper right
   highlights **aeroplane (0.00)** and **chair (0.04)**, while dotted teal links
   connect the probability lists to their classifier outputs.

Do not invent details that are not visible. Do not mention this instruction, the
examples, file names, image paths, or the style example. Return only the final
description, using numbered sentences or paragraphs when that improves clarity.
You may use lightweight Markdown for readability: headings, numbered or bulleted
lists, bold text, inline code, links, ==highlighted text==, and ++underlined
text++ are supported by the local reviewer.
