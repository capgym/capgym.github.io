## Overview

Welcome. You are designing a website for showcasing an academic research paper called CaP-X. It is a benchmark for evaluation the performance of LLM agents on physical robotics tasks.

## Website Sections

### Title and Navigation Bar

This section is very similar to https://doorman-humanoid.github.io/.

Navigation bar: always stick on top. Left side: CaP-X. Right side: NVIDIA GEAR Team. Center: Buttons: Home, arXiv, Code, Playground. Playground button should be highlighted.

Title: Paper name.

Authors: list all with homepage hyperlink. list affiliations. 
List logos of all institutions. Mono color style.

### AI Progress on CaP-X

Main figure like in HLE (https://agi.safe.ai/). The overall success rate of various models over time. X axis: date time. Y axis: success rate. Model data points use the icon of their company (institution) logo. Detail can be extended when hovering over the icon. The upper bound of all models at all times (the best model performance) is connected via a dotted spline.

### CTA Button

The playground button will take the audience to a separate website that will allow human to interact with the coding agent in a simulator. It is the same place that the playground button in the nav bar will take. The link is TBD.

The left side is the text and button. The right side is left blank later for some eye-catching figure of the playground.

### Introduction

This section has a eye-catching title like "Benchmarking LM Agents on Embodied Intelligance Tasks". It goes into depth to advertise the details, covering the simulation benchmarks included, the real-world deployment readiness, etc.

Then there will be a gallery of real and sim result videos.

### Highlights

This section has a series of highlight titles that calls out the various conclusions of the paper, followed by some figure and text that support them. Some rudementary ideas:

1. Frontier model can work directly on today’s robotics benchmarks with non-zero success rate. (Supported by: Figure 1)
2. VLM Agents can zero-shot on LIBERO-PRO. SoTA VLA (Pi 0.5) cannot. (Supported by: Table 2)
3. Post-training makes VLM Agent better on robotics tasks. (Supported by: Table 4)
4. Smaller models catch up when only abstract reasoning is needed. (Supported by: Figure 2)

## Visuals

This project is done at NVIDIA so it should use the NVIDIA theme.

The main visual could look something similar to https://doorman-humanoid.github.io/, but with one important distinction: that website uses a dark background + nvidia green color, whereas we want to use a light (white) background + nvidia green color.

The builder of this website was kind enough to leave a document explaining how everything is done: https://github.com/doorman-humanoid/doorman-humanoid.github.io/blob/main/CLAUDE.md. You should take a look, especially when it comes to the interactiveness of figures since we will have a lot of those.

Finally, we want to have some fancy but subtle animation, which you can also find traces of in the website above. In particular, we want to take full advantage of GSAP (https://gsap.com/docs/v3/) and maybe other animation library to make the website look as complete, modern, and slick as possible.

## Important Considerations

After this website is finished, we will proceed with making an anonymous version of the website with the exact same information except masking all author and affiliation information. it is therefore crucial that these anonymity-breaching information are put in a centralized location and can be removed easily. This also extends to external links such as arXiv, Google Tag, and demo website.

All content in information/ will be thrown out at production time. Make a copy of anything that will go to production.

Ask me for clarifications instead of speculating for answers.

## Information

### Paper

Paper name: CaP-X: A Framework for Benchmarking and Improving Coding Agents for Robot Manipulation
Authors: (* indicates equal contribution.)

- Max Fu*[1,2] (https://max-fu.github.io/)
- Justin Yu*[2] (https://uynitsuj.github.io/)
- Karim El-Refai*[2] (https://el-refai.github.io/)
- Ethan Kou*[2] (https://www.linkedin.com/in/ethan-kou-507b25288/)
- Haoru Xue*[1,2] (https://haoruxue.github.io/)
- Huang Huang[3] (https://qingh097.github.io/)
- Wenli Xiao[4] (https://www.wenlixiao.com/)
- Guanzhi Wang[1] (https://guanzhi.me/)
- Fei-Fei Li[3] (https://profiles.stanford.edu/fei-fei-li)
- Jiajun Wu[3] (https://jiajunwu.com/)
- Shankar Sastry[2] (https://www2.eecs.berkeley.edu/Faculty/Homepages/sastry.html)
- Yuke Zhu[1] (https://yukezhu.me/)
- Ken Goldberg[2] (https://www2.eecs.berkeley.edu/Faculty/Homepages/goldberg.html)
- Jim "Linxi" Fan[1] (https://jimfan.me/)

[1] NVIDIA [2] UC Berkeley [3] Stanford [4] CMU

File path: information/capgym_icml26.pdf

### Google Tag

You can find the google tag in information/gtag.html. Do not refer to this file in the final product as it will be removed.

### Raw data for plots

Raw data and the original visualization scripts are in information/HyRL-visualization. information/HyRL-visualization/model_timeline.py was used to produce the main splash figure in the paper. Other figures will be added to the website later.
