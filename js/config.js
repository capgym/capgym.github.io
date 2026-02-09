/**
 * CaP-X Website Configuration
 *
 * This file contains ALL anonymizable information.
 * For double-blind review, replace this file with an anonymized version.
 */
const SITE_CONFIG = {
  // Paper metadata
  paperTitle: "CaP-X: A Framework for Benchmarking and Improving Coding Agents for Robot Manipulation",

  // Team branding (nav bar right side)
  teamName: "NVIDIA GEAR Team",

  // Navigation links (set to '#' for placeholders)
  links: {
    arxiv: "#",
    code: "#",
    playground: "#",
  },

  // Google Analytics tag ID (set to null to disable)
  gtagId: "G-XV8XWV268L",

  // Authors list
  authors: [
    { name: "Max Fu", url: "https://max-fu.github.io/", affiliations: [1, 2], equalContrib: true },
    { name: "Justin Yu", url: "https://uynitsuj.github.io/", affiliations: [2], equalContrib: true },
    { name: "Karim El-Refai", url: "https://el-refai.github.io/", affiliations: [2], equalContrib: true },
    { name: "Ethan Kou", url: "https://www.linkedin.com/in/ethan-kou-507b25288/", affiliations: [2], equalContrib: true },
    { name: "Haoru Xue", url: "https://haoruxue.github.io/", affiliations: [1, 2], equalContrib: true },
    { name: "Huang Huang", url: "https://qingh097.github.io/", affiliations: [3], equalContrib: false },
    { name: "Wenli Xiao", url: "https://www.wenlixiao.com/", affiliations: [4], equalContrib: false },
    { name: "Guanzhi Wang", url: "https://guanzhi.me/", affiliations: [1], equalContrib: false },
    { name: "Fei-Fei Li", url: "https://profiles.stanford.edu/fei-fei-li", affiliations: [3], equalContrib: false },
    { name: "Jiajun Wu", url: "https://jiajunwu.com/", affiliations: [3], equalContrib: false },
    { name: "Shankar Sastry", url: "https://www2.eecs.berkeley.edu/Faculty/Homepages/sastry.html", affiliations: [2], equalContrib: false },
    { name: "Yuke Zhu", url: "https://yukezhu.me/", affiliations: [1], equalContrib: false },
    { name: "Ken Goldberg", url: "https://www2.eecs.berkeley.edu/Faculty/Homepages/goldberg.html", affiliations: [2], equalContrib: false },
    { name: "Jim \"Linxi\" Fan", url: "https://jimfan.me/", affiliations: [1], equalContrib: false },
  ],

  // Affiliations
  affiliations: {
    1: "NVIDIA",
    2: "UC Berkeley",
    3: "Stanford",
    4: "CMU",
  },

  // Institution logo config (text placeholders for now)
  institutionLogos: [
    { name: "NVIDIA", id: 1 },
    { name: "UC Berkeley", id: 2 },
    { name: "Stanford", id: 3 },
    { name: "CMU", id: 4 },
  ],
};

// Inject Google Analytics if configured
if (SITE_CONFIG.gtagId) {
  const gtagScript = document.createElement("script");
  gtagScript.async = true;
  gtagScript.src = `https://www.googletagmanager.com/gtag/js?id=${SITE_CONFIG.gtagId}`;
  document.head.appendChild(gtagScript);

  window.dataLayer = window.dataLayer || [];
  function gtag() { dataLayer.push(arguments); }
  gtag("js", new Date());
  gtag("config", SITE_CONFIG.gtagId);
}
