(() => {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const header = document.querySelector("#site-header");
  const progressBar = document.querySelector("#scroll-progress-bar");

  const updateScroll = () => {
    const scrollTop = window.scrollY;
    const scrollable = document.documentElement.scrollHeight - window.innerHeight;
    const progress = scrollable > 0 ? scrollTop / scrollable : 0;
    progressBar.style.width = `${Math.min(progress * 100, 100)}%`;
    header.classList.toggle("is-scrolled", scrollTop > 24);
  };

  updateScroll();
  window.addEventListener("scroll", updateScroll, { passive: true });

  const menuButton = document.querySelector(".menu-toggle");
  const mainNav = document.querySelector("#main-nav");

  const closeMenu = () => {
    mainNav.classList.remove("is-open");
    menuButton.setAttribute("aria-expanded", "false");
    menuButton.setAttribute("aria-label", "打开导航菜单");
  };

  menuButton.addEventListener("click", () => {
    const shouldOpen = menuButton.getAttribute("aria-expanded") !== "true";
    mainNav.classList.toggle("is-open", shouldOpen);
    menuButton.setAttribute("aria-expanded", String(shouldOpen));
    menuButton.setAttribute("aria-label", shouldOpen ? "关闭导航菜单" : "打开导航菜单");
  });

  mainNav.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));

  document.addEventListener("click", (event) => {
    if (!mainNav.classList.contains("is-open")) return;
    if (mainNav.contains(event.target) || menuButton.contains(event.target)) return;
    closeMenu();
  });

  const revealItems = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && !reducedMotion) {
    const revealObserver = new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -7% 0px" },
    );
    revealItems.forEach((item) => revealObserver.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add("is-visible"));
  }

  const navLinks = [...document.querySelectorAll(".main-nav a")];
  const navSections = navLinks
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);

  if ("IntersectionObserver" in window) {
    const navObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          navLinks.forEach((link) => {
            link.classList.toggle("is-active", link.getAttribute("href") === `#${entry.target.id}`);
          });
        });
      },
      { rootMargin: "-24% 0px -62% 0px" },
    );
    navSections.forEach((section) => navObserver.observe(section));
  }

  const scanCard = document.querySelector("#scan-card");
  const heroVisual = document.querySelector(".hero-visual");

  if (scanCard && heroVisual && !reducedMotion && window.matchMedia("(pointer:fine)").matches) {
    let targetTiltX = 0;
    let targetTiltY = 0;
    let currentTiltX = 0;
    let currentTiltY = 0;
    let tiltFrame = null;

    const renderTilt = () => {
      currentTiltX += (targetTiltX - currentTiltX) * 0.1;
      currentTiltY += (targetTiltY - currentTiltY) * 0.1;
      scanCard.style.setProperty("--rx", `${currentTiltX.toFixed(3)}deg`);
      scanCard.style.setProperty("--ry", `${currentTiltY.toFixed(3)}deg`);
      if (
        Math.abs(currentTiltX - targetTiltX) > 0.01 ||
        Math.abs(currentTiltY - targetTiltY) > 0.01
      ) {
        tiltFrame = requestAnimationFrame(renderTilt);
      } else {
        tiltFrame = null;
      }
    };

    const requestTilt = () => {
      if (!tiltFrame) tiltFrame = requestAnimationFrame(renderTilt);
    };

    heroVisual.addEventListener("pointermove", (event) => {
      const rect = heroVisual.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width - 0.5;
      const y = (event.clientY - rect.top) / rect.height - 0.5;
      targetTiltX = -y * 4.5;
      targetTiltY = x * 5.5;
      requestTilt();
    });
    heroVisual.addEventListener("pointerleave", () => {
      targetTiltX = 0;
      targetTiltY = 0;
      requestTilt();
    });
  }

  const experiments = {
    a: {
      status: "BASELINE / A",
      title: "建立纵向生成的最低基线",
      description:
        "只使用历史影像与肿瘤掩码，验证模型能否学习时间点之间的基本变化。该组不引入任何临床语义，用于判断其他条件是否真正带来增益。",
      condition: "时间间隔 Δt",
      coreTitle: "DIFFUSION",
      coreCaption: "影像条件生成",
      output: "未来影像",
      purpose: "控制变量基线",
    },
    b: {
      status: "STRUCTURED / B",
      title: "用简洁的表格条件建立强参照",
      description:
        "将治疗类别、随访间隔和必要的临床变量编码为表格向量，与影像条件联合输入。它是在当前数据条件下最稳健、最应优先验证的方案。",
      condition: "治疗类别 + Δt",
      coreTitle: "TABULAR COND.",
      coreCaption: "结构化临床条件",
      output: "影像 + 掩码",
      purpose: "主参照模型",
    },
    c: {
      status: "LANGUAGE / C",
      title: "检验语言模型是否真的有额外价值",
      description:
        "只把已有结构化变量模板化为短文本，再由语言模型编码。我们不生成不存在的病情，也不使用后续信息，重点检验语言先验能否改善条件表达。",
      condition: "模板化临床变量",
      coreTitle: "LLM ENCODER",
      coreCaption: "语言条件编码",
      output: "条件轨迹",
      purpose: "语言先验增益",
    },
    d: {
      status: "ROBUSTNESS / D",
      title: "在信息不完整时保持生成稳定",
      description:
        "随机屏蔽一个或多个 MRI 模态，并加入条件缺失场景。对比不同编码方式的性能下降幅度，验证模型在真实数据不完整时是否仍然可靠。",
      condition: "缺失标记 + Δt",
      coreTitle: "MASKED COND.",
      coreCaption: "缺失条件训练",
      output: "不确定性",
      purpose: "跨模态鲁棒性",
    },
  };

  const experimentTabs = [...document.querySelectorAll(".experiment-tab")];
  experimentTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const selected = experiments[tab.dataset.experiment];
      if (!selected) return;
      experimentTabs.forEach((item) => {
        const active = item === tab;
        item.classList.toggle("is-active", active);
        item.setAttribute("aria-selected", String(active));
      });
      document.querySelector("#experiment-status").textContent = selected.status;
      document.querySelector("#experiment-title").textContent = selected.title;
      document.querySelector("#experiment-description").textContent = selected.description;
      document.querySelector("#condition-input").textContent = selected.condition;
      document.querySelector("#core-title").textContent = selected.coreTitle;
      document.querySelector("#core-caption").textContent = selected.coreCaption;
      document.querySelector("#output-title").textContent = selected.output;
      document.querySelector("#experiment-purpose").textContent = selected.purpose;
    });
  });

  const copyText = async (text) => {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }

    const helper = document.createElement("textarea");
    helper.value = text;
    helper.setAttribute("readonly", "");
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.appendChild(helper);
    helper.select();
    const copied = document.execCommand("copy");
    helper.remove();
    return copied;
  };

  const modalityButtons = [...document.querySelectorAll(".modality-toggle")];
  const conditionButtons = [...document.querySelectorAll(".condition-toggle")];
  const configCode = document.querySelector("#config-code");
  const lineNumbers = document.querySelector(".line-numbers");
  const configCount = document.querySelector("#config-count");
  const configStatus = document.querySelector("#config-status");
  const copySpecButton = document.querySelector("#copy-spec");
  const conditionKeys = {
    temporal: "随访时间间隔",
    treatment: "结构化治疗变量",
    language: "语言化条件编码",
    missing: "缺失模态鲁棒性",
  };

  const getBuildConfig = () => {
    const modalities = modalityButtons
      .filter((button) => button.classList.contains("is-on"))
      .map((button) => button.dataset.modality);
    const conditions = Object.fromEntries(
      conditionButtons.map((button) => [
        button.dataset.condition,
        button.classList.contains("is-on"),
      ]),
    );
    return {
      modalities,
      conditions,
      object: {
        project: "PRISM",
        objective: ["future_mri_generation", "survival_risk"],
        modalities,
        condition: {
          history: true,
          delta_t: conditions.temporal,
          treatment: conditions.treatment ? "tabular" : null,
          language_encoder: conditions.language ? "llm_adapter" : null,
          missing_robustness: conditions.missing,
        },
        outputs: ["mri_t+n", "tumor_mask", "uncertainty"],
        evaluation: ["dice", "c_index", "calibration"],
        split: "patient_level",
      },
    };
  };

  const highlightJson = (json) => {
    const escaped = json
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");

    return escaped
      .replace(/("(?:\\u[\da-fA-F]{4}|\\[^u]|[^\\"])*")(\s*:)?/g, (match, token, colon) => {
        const className = colon ? "json-key" : "json-string";
        return `<span class="${className}">${token}</span>${colon || ""}`;
      })
      .replace(/\b(true|false|null)\b/g, '<span class="json-boolean">$1</span>');
  };

  let currentBuildSpec = "";

  const updateBuildSpec = () => {
    const config = getBuildConfig();
    currentBuildSpec = JSON.stringify(config.object, null, 2);
    configCode.innerHTML = highlightJson(currentBuildSpec);
    lineNumbers.innerHTML = currentBuildSpec
      .split("\n")
      .map((_, index) => `<span>${String(index + 1).padStart(2, "0")}</span>`)
      .join("");

    const conditionCount = Object.values(config.conditions).filter(Boolean).length;
    configCount.textContent = `${config.modalities.length} MODALITIES · ${conditionCount} CONDITIONS`;
    configStatus.textContent = config.modalities.length > 0 ? "CONFIG VALID" : "SELECT A MODALITY";
    copySpecButton.disabled = config.modalities.length === 0;
  };

  modalityButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const activeCount = modalityButtons.filter((item) =>
        item.classList.contains("is-on"),
      ).length;
      if (button.classList.contains("is-on") && activeCount === 1) return;
      const active = !button.classList.contains("is-on");
      button.classList.toggle("is-on", active);
      button.setAttribute("aria-pressed", String(active));
      updateBuildSpec();
    });
  });

  conditionButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const active = !button.classList.contains("is-on");
      button.classList.toggle("is-on", active);
      button.setAttribute("aria-pressed", String(active));
      updateBuildSpec();
    });
  });

  copySpecButton.addEventListener("click", async () => {
    if (!currentBuildSpec) return;
    const copied = await copyText(currentBuildSpec);
    copySpecButton.classList.toggle("is-copied", copied);
    const label = copySpecButton.querySelector("span");
    label.textContent = copied ? "SPEC COPIED" : "COPY FAILED";
    window.setTimeout(() => {
      copySpecButton.classList.remove("is-copied");
      label.textContent = "COPY BUILD SPEC";
    }, 1800);
  });

  updateBuildSpec();

  const routeSteps = [
    {
      kicker: "STAGE 01 / DATA FOUNDATION",
      badge: "FOUNDATION",
      title: "把随访数据变成可复核的实验资产",
      description:
        "完成多模态配准、重采样、强度标准化、肿瘤亚区处理和患者级划分；建立纵向影像、治疗信息、随访间隔与删失标签的统一数据表。",
      output: "统一数据表 + 数据字典",
      meter: "92%",
      meterLabel: "HIGH",
    },
    {
      kicker: "STAGE 02 / STATIC BASELINE",
      badge: "BASELINE",
      title: "用 Med-DDPM 建立可比较的静态起点",
      description:
        "复现四模态条件生成、导出、切片和轮廓叠加流程；固定数据处理与评价口径，让后续纵向模型拥有明确、可复现的参照。",
      output: "静态生成基线 + 管线日志",
      meter: "72%",
      meterLabel: "HIGH",
    },
    {
      kicker: "STAGE 03 / LONGITUDINAL GENERATION",
      badge: "CORE",
      title: "让时间、治疗与缺失模态成为条件",
      description:
        "输入历史影像、掩码、Δt 与结构化治疗信息，输出下一时间点影像、肿瘤掩码和不确定性；比较双条件、语言化条件及缺失模态训练。",
      output: "未来状态生成器 + 消融矩阵",
      meter: "84%",
      meterLabel: "CORE",
    },
    {
      kicker: "STAGE 04 / PROGNOSIS COUPLING",
      badge: "PREDICTION",
      title: "从生成轨迹中提取动态预后信号",
      description:
        "构建体积变化率、水肿范围梯度和增强模式轨迹等特征，接入 Cox 或离散时间生存模型，并与静态影像基线比较增量价值。",
      output: "风险评分 + 增量预后结果",
      meter: "70%",
      meterLabel: "KEY",
    },
    {
      kicker: "STAGE 05 / SYSTEM VALIDATION",
      badge: "EVIDENCE",
      title: "用患者级留出集完成闭环验证",
      description:
        "固定划分、随机种子和模型配置，完成生成质量、肿瘤一致性、生存效用与校准分析；汇总负面结果、失败样例和可复现实验材料。",
      output: "验证报告 + 科研演示原型",
      meter: "88%",
      meterLabel: "FINAL",
    },
  ];

  const routeStepButtons = [...document.querySelectorAll(".route-step")];
  routeStepButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.step);
      const data = routeSteps[index];
      if (!data) return;

      routeStepButtons.forEach((item) => {
        const active = item === button;
        item.classList.toggle("is-active", active);
        item.setAttribute("aria-selected", String(active));
      });

      document.querySelector("#route-kicker").textContent = data.kicker;
      document.querySelector("#route-badge").textContent = data.badge;
      document.querySelector("#route-title").textContent = data.title;
      document.querySelector("#route-description").textContent = data.description;
      document.querySelector("#route-output").textContent = data.output;
      document.querySelector("#route-meter-label").textContent = data.meterLabel;
      document.querySelector("#route-meter-fill").style.width = data.meter;
      document.querySelector("#route-progress-fill").style.width = `${(index / (routeSteps.length - 1)) * 100}%`;
    });
  });

  const commandPalette = document.querySelector("#command-palette");
  const commandTrigger = document.querySelector(".command-trigger");
  const commandCloseButton = document.querySelector("[data-command-close]");
  const commandInput = document.querySelector("#command-input");
  const commandButtons = [...document.querySelectorAll("#command-list > button")];
  const commandEmpty = document.querySelector("#command-empty");
  let selectedCommandIndex = 0;

  const visibleCommands = () =>
    commandButtons.filter((button) => !button.hidden && !button.disabled);

  const setCommandSelection = (index) => {
    const commands = visibleCommands();
    if (commands.length === 0) return;
    selectedCommandIndex = (index + commands.length) % commands.length;
    commandButtons.forEach((button) => button.classList.remove("is-selected"));
    commands[selectedCommandIndex].classList.add("is-selected");
    commands[selectedCommandIndex].scrollIntoView({ block: "nearest" });
  };

  const openCommandPalette = () => {
    if (commandPalette.open) return;
    commandPalette.showModal();
    document.body.classList.add("modal-open");
    commandTrigger.setAttribute("aria-expanded", "true");
    commandInput.value = "";
    commandButtons.forEach((button) => {
      button.hidden = false;
      button.classList.remove("is-selected");
    });
    commandEmpty.hidden = true;
    selectedCommandIndex = 0;
    setCommandSelection(0);
    window.setTimeout(() => commandInput.focus(), 30);
  };

  const closeCommandPalette = () => {
    if (!commandPalette.open) return;
    commandPalette.close();
  };

  commandTrigger.addEventListener("click", openCommandPalette);
  commandCloseButton.addEventListener("click", closeCommandPalette);
  commandPalette.addEventListener("close", () => {
    document.body.classList.remove("modal-open");
    commandTrigger.setAttribute("aria-expanded", "false");
  });
  commandPalette.addEventListener("click", (event) => {
    if (event.target === commandPalette) closeCommandPalette();
  });

  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      if (commandPalette.open) closeCommandPalette();
      else if (!modal.open) openCommandPalette();
      return;
    }

    if (!commandPalette.open) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setCommandSelection(selectedCommandIndex + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setCommandSelection(selectedCommandIndex - 1);
    } else if (event.key === "Enter") {
      const commands = visibleCommands();
      if (commands[selectedCommandIndex]) {
        event.preventDefault();
        commands[selectedCommandIndex].click();
      }
    }
  });

  commandInput.addEventListener("input", () => {
    const query = commandInput.value.trim().toLowerCase();
    commandButtons.forEach((button) => {
      button.hidden = !button.textContent.toLowerCase().includes(query);
      button.classList.remove("is-selected");
    });
    const commands = visibleCommands();
    commandEmpty.hidden = commands.length > 0;
    selectedCommandIndex = 0;
    if (commands[0]) commands[0].classList.add("is-selected");
  });

  commandButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      const target = button.dataset.commandTarget;
      if (target) {
        closeCommandPalette();
        window.setTimeout(() => {
          document.querySelector(target)?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 80);
        return;
      }

      if ("commandCopy" in button.dataset) {
        const summary =
          "PRISM｜基于多模态的脑肿瘤纵向生成与预后预测。以历史多模态 MRI、治疗信息与随访间隔为条件，生成未来影像、肿瘤掩码和不确定性，并验证动态特征的生存预后增量价值。仅用于科研验证。";
        const copied = await copyText(summary);
        button.querySelector("small").textContent = copied ? "项目摘要已复制" : "复制失败，请重试";
      }
    });
  });

  const modal = document.querySelector("#prototype-modal");
  const modalOpenButton = document.querySelector("[data-modal-open]");
  const modalCloseButton = document.querySelector("[data-modal-close]");

  const closeModal = () => {
    if (!modal.open) return;
    modal.close();
    document.body.classList.remove("modal-open");
  };

  modalOpenButton.addEventListener("click", () => {
    modal.showModal();
    document.body.classList.add("modal-open");
  });
  modalCloseButton.addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });
  modal.addEventListener("close", () => document.body.classList.remove("modal-open"));

  const canvas = document.querySelector("#signal-canvas");
  const context = canvas.getContext("2d");

  if (context && !reducedMotion) {
    let width = 0;
    let height = 0;
    let dpr = 1;
    let points = [];
    let frameId = null;
    let pointerX = 0;
    let pointerY = 0;

    const resizeCanvas = () => {
      const rect = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.max(22, Math.min(54, Math.floor(width / 24)));
      points = Array.from({ length: count }, (_, index) => ({
        x: (index * 97.31) % width,
        y: (index * 41.79 + index * index * 1.7) % height,
        r: 0.5 + ((index * 7) % 12) / 12,
        phase: index * 0.63,
        speed: 0.08 + ((index * 11) % 9) / 70,
      }));
    };

    const draw = (time) => {
      context.clearRect(0, 0, width, height);
      const seconds = time * 0.001;

      points.forEach((point, index) => {
        const driftX = Math.sin(seconds * point.speed + point.phase) * 22;
        const driftY = Math.cos(seconds * point.speed * 0.8 + point.phase) * 12;
        const x = point.x + driftX;
        const y = point.y + driftY;
        const distance = Math.hypot(x - pointerX, y - pointerY);
        const glow = Math.max(0, 1 - distance / 240);
        const alpha = 0.08 + glow * 0.34;

        if (index > 0) {
          const previous = points[index - 1];
          const previousX = previous.x + Math.sin(seconds * previous.speed + previous.phase) * 22;
          const previousY = previous.y + Math.cos(seconds * previous.speed * 0.8 + previous.phase) * 12;
          if (Math.hypot(previousX - x, previousY - y) < 180) {
            context.beginPath();
            context.moveTo(previousX, previousY);
            context.lineTo(x, y);
            context.strokeStyle = `rgba(156, 245, 199, ${0.025 + glow * 0.04})`;
            context.lineWidth = 0.6;
            context.stroke();
          }
        }

        context.beginPath();
        context.arc(x, y, point.r + glow * 0.8, 0, Math.PI * 2);
        context.fillStyle =
          index % 9 === 0
            ? `rgba(255, 137, 108, ${alpha})`
            : `rgba(156, 245, 199, ${alpha})`;
        context.fill();
      });

      const gradient = context.createRadialGradient(
        pointerX,
        pointerY,
        0,
        pointerX,
        pointerY,
        160,
      );
      gradient.addColorStop(0, "rgba(156, 245, 199, 0.032)");
      gradient.addColorStop(1, "rgba(156, 245, 199, 0)");
      context.fillStyle = gradient;
      context.fillRect(pointerX - 160, pointerY - 160, 320, 320);

      frameId = requestAnimationFrame(draw);
    };

    const handlePointer = (event) => {
      const rect = canvas.getBoundingClientRect();
      pointerX = event.clientX - rect.left;
      pointerY = event.clientY - rect.top;
    };

    resizeCanvas();
    pointerX = width * 0.64;
    pointerY = height * 0.46;
    window.addEventListener("resize", resizeCanvas, { passive: true });
    window.addEventListener("pointermove", handlePointer, { passive: true });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && frameId) {
        cancelAnimationFrame(frameId);
        frameId = null;
      } else if (!document.hidden && !frameId) {
        frameId = requestAnimationFrame(draw);
      }
    });
    frameId = requestAnimationFrame(draw);
  }

  const storySection = document.querySelector("#data-story");
  const storyScrolly = document.querySelector("#story-scrolly");
  const storyCanvas = document.querySelector("#data-story-canvas");

  if (storySection && storyScrolly && storyCanvas) {
    const storyContext = storyCanvas.getContext("2d");
    const storySteps = [...document.querySelectorAll("[data-story-step]")];
    const storyProgressDots = [...document.querySelectorAll(".story-step-progress span")];
    const storyStepNumber = document.querySelector("#story-step-number");
    const storyDrawnValue = document.querySelector("#story-drawn-value");
    const points = [
      { label: "T1", value: 14.693, color: "#9cf5c7" },
      { label: "T1CE", value: 14.754, color: "#9cf5c7" },
      { label: "T2", value: 15.763, color: "#ff896c" },
      { label: "FLAIR", value: 11.234, color: "#9cf5c7" },
    ];
    const mean = points.reduce((sum, point) => sum + point.value, 0) / points.length;
    const sourceImage = new Image();
    let storyWidth = 0;
    let storyHeight = 0;
    let storyDpr = 1;
    let storyFrame = null;
    let storyVisible = false;
    let targetProgress = 0;
    let smoothProgress = 0;
    let activeStoryStep = -1;
    let lastStoryTime = 0;
    let sourceDots = [];
    let imageReady = false;

    const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
    const lerp = (start, end, amount) => start + (end - start) * amount;
    const smoothstep = (min, max, value) => {
      const x = clamp((value - min) / (max - min));
      return x * x * (3 - 2 * x);
    };
    const hash = (x, y) => {
      const value = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
      return value - Math.floor(value);
    };

    const layoutStoryCanvas = () => {
      const rect = storyCanvas.getBoundingClientRect();
      storyDpr = Math.min(window.devicePixelRatio || 1, 2);
      storyWidth = rect.width;
      storyHeight = rect.height;
      storyCanvas.width = Math.round(storyWidth * storyDpr);
      storyCanvas.height = Math.round(storyHeight * storyDpr);
      storyContext.setTransform(storyDpr, 0, 0, storyDpr, 0, 0);
    };

    const chartGeometry = () => {
      const compact = storyWidth < 550;
      const left = compact ? 35 : 52;
      const right = compact ? 22 : 34;
      const top = compact ? 46 : 52;
      const bottom = compact ? 44 : 50;
      const plotWidth = Math.max(1, storyWidth - left - right);
      const plotHeight = Math.max(1, storyHeight - top - bottom);
      const yForValue = (value) => top + plotHeight - (value / 18) * plotHeight;
      const pointList = points.map((point, index) => ({
        ...point,
        x: left + plotWidth * (0.16 + index * 0.225),
        y: yForValue(point.value),
      }));
      return { compact, left, right, top, bottom, plotWidth, plotHeight, yForValue, points: pointList };
    };

    const buildDotField = () => {
      if (!imageReady || !sourceImage.naturalWidth) return;
      const sampleSize = 76;
      const sampleCanvas = document.createElement("canvas");
      sampleCanvas.width = sampleSize;
      sampleCanvas.height = sampleSize;
      const sampleContext = sampleCanvas.getContext("2d", { willReadFrequently: true });
      sampleContext.drawImage(sourceImage, 0, 0, sampleSize, sampleSize);
      const pixels = sampleContext.getImageData(0, 0, sampleSize, sampleSize).data;
      const candidates = [];

      for (let y = 0; y < sampleSize; y += 1) {
        for (let x = 0; x < sampleSize; x += 1) {
          const pixelIndex = (y * sampleSize + x) * 4;
          const luminance =
            (pixels[pixelIndex] * 0.2126 +
              pixels[pixelIndex + 1] * 0.7152 +
              pixels[pixelIndex + 2] * 0.0722) /
            255;
          if (luminance < 0.075) continue;

          const seed = hash(x + 1, y + 3);
          const modalityIndex = Math.floor(seed * points.length);
          const value = points[modalityIndex].value;
          candidates.push({
            x,
            y,
            luminance,
            seed,
            modalityIndex,
            radius: 0.55 + luminance * 1.25,
            targetY: 0.055 + hash(y + 7.1, x + 9.7) * (value / 18) * 0.82,
          });
        }
      }

      sourceDots = candidates
        .filter((_, index) => index % Math.max(1, Math.ceil(candidates.length / 2200)) === 0)
        .map((dot) => ({
          ...dot,
          x: dot.x / sampleSize,
          y: dot.y / sampleSize,
        }));
    };

    const buildFallbackDotField = () => {
      sourceDots = [];
      const size = 76;
      for (let y = 0; y < size; y += 1) {
        for (let x = 0; x < size; x += 1) {
          const nx = (x / size - 0.5) / 0.35;
          const ny = (y / size - 0.5) / 0.44;
          const seed = hash(x + 2, y + 4);
          if (nx * nx + ny * ny > 1 || seed < 0.12) continue;
          const modalityIndex = Math.floor(seed * points.length);
          sourceDots.push({
            x: x / size,
            y: y / size,
            luminance: 0.35 + (1 - Math.min(1, nx * nx + ny * ny)) * 0.55,
            seed,
            modalityIndex,
            radius: 0.65 + seed * 1.25,
            targetY: 0.05 + hash(y + 4, x + 8) * (points[modalityIndex].value / 18) * 0.84,
          });
        }
      }
    };

    const setStoryStep = (nextStep) => {
      if (nextStep === activeStoryStep) return;
      activeStoryStep = nextStep;
      storyProgressDots.forEach((dot, index) => {
        dot.classList.toggle("is-active", index === nextStep);
      });
      storyStepNumber.textContent = `0${nextStep + 1}`;
    };

    const updateStoryNarrative = (progress) => {
      const alphas = [
        1 - smoothstep(0.2, 0.32, progress),
        smoothstep(0.21, 0.33, progress) * (1 - smoothstep(0.62, 0.74, progress)),
        smoothstep(0.63, 0.76, progress),
      ];
      const nextStep = progress < 0.3 ? 0 : progress < 0.73 ? 1 : 2;
      setStoryStep(nextStep);

      storySteps.forEach((step, index) => {
        const alpha = alphas[index];
        const direction = index < nextStep ? -1 : 1;
        step.style.opacity = alpha.toFixed(3);
        step.style.transform = `translateY(${((1 - alpha) * 18 * direction).toFixed(2)}px)`;
        step.style.visibility = alpha > 0.01 ? "visible" : "hidden";
        step.setAttribute("aria-hidden", String(index !== nextStep));
      });

      if (progress < 0.27) {
        storyDrawnValue.textContent = "IMAGE / DOT FIELD";
      } else if (progress < 0.78) {
        storyDrawnValue.textContent = `MORPH / ${Math.round(progress * 100)}%`;
      } else {
        storyDrawnValue.textContent = "PSNR / 4 MODALITIES";
      }
    };

    const drawStory = (time) => {
      const delta = Math.min(32, time - lastStoryTime || 16);
      lastStoryTime = time;
      smoothProgress = reducedMotion
        ? targetProgress
        : lerp(smoothProgress, targetProgress, 1 - Math.pow(0.86, delta / 16));
      updateStoryNarrative(smoothProgress);

      const chart = chartGeometry();
      const axisBottom = chart.top + chart.plotHeight;
      const sourceSide = Math.min(storyWidth * 0.66, storyHeight * 0.82);
      const sourceX = storyWidth * 0.46;
      const sourceY = storyHeight * 0.48;
      const axisAlpha = smoothstep(0.28, 0.54, smoothProgress);
      const dataAlpha = smoothstep(0.48, 0.8, smoothProgress);
      const meanAlpha = smoothstep(0.76, 0.92, smoothProgress);
      const tick = Math.floor(time / 105);

      storyContext.clearRect(0, 0, storyWidth, storyHeight);
      storyContext.save();
      storyContext.globalAlpha = axisAlpha * 0.8;
      storyContext.strokeStyle = "rgba(149, 162, 157, 0.52)";
      storyContext.lineWidth = 1;
      storyContext.beginPath();
      storyContext.moveTo(chart.left, axisBottom);
      storyContext.lineTo(chart.left, chart.top);
      storyContext.moveTo(chart.left, axisBottom);
      storyContext.lineTo(chart.left + chart.plotWidth, axisBottom);
      storyContext.stroke();

      [0, 6, 12, 18].forEach((value) => {
        const y = chart.yForValue(value);
        storyContext.setLineDash([3, 7]);
        storyContext.strokeStyle = "rgba(149, 162, 157, 0.18)";
        storyContext.beginPath();
        storyContext.moveTo(chart.left, y);
        storyContext.lineTo(chart.left + chart.plotWidth, y);
        storyContext.stroke();
        storyContext.setLineDash([]);
        storyContext.fillStyle = "rgba(149, 162, 157, 0.7)";
        storyContext.font = '9px "Cascadia Mono", Consolas, monospace';
        storyContext.fillText(String(value), Math.max(5, chart.left - 25), y + 3);
      });
      storyContext.restore();

      sourceDots.forEach((dot) => {
        const destinationX =
          chart.left +
          chart.plotWidth * (0.16 + dot.modalityIndex * 0.225) +
          (hash(dot.x * 94, dot.y * 87) - 0.5) * chart.plotWidth * 0.1;
        const destinationY = chart.top + chart.plotHeight * dot.targetY;
        const delay = dot.seed * 0.17;
        const local = clamp((smoothProgress - 0.08 - delay) / 0.57);
        const eased = local * local * (3 - 2 * local);
        const onFront = local > 0.02 && local < 0.98 && Math.abs(dot.seed - local) < 0.1;
        const flicker = onFront && hash(dot.x * 1000 + tick, dot.y * 900) > 0.48 ? 0.42 : 1;
        const stripe = hash(Math.floor(dot.y * 76), tick) > 0.972 ? (dot.seed - 0.5) * 16 : 0;
        const dx = sourceX + (dot.x - 0.5) * sourceSide;
        const dy = sourceY + (dot.y - 0.5) * sourceSide;
        const x = lerp(dx, destinationX, eased) + stripe * Math.sin(local * Math.PI);
        const y = lerp(dy, destinationY, eased);
        const color = eased > 0.5 ? points[dot.modalityIndex].color : "#9cf5c7";
        const alpha =
          (0.16 + dot.luminance * 0.56) * (1 - dataAlpha * 0.16) * flicker;
        const radius = lerp(dot.radius, chart.compact ? 1.3 : 1.65, eased);

        storyContext.beginPath();
        storyContext.arc(x, y, radius, 0, Math.PI * 2);
        storyContext.fillStyle = color;
        storyContext.globalAlpha = alpha;
        storyContext.fill();
      });

      storyContext.globalAlpha = 1;
      if (dataAlpha > 0.01) {
        chart.points.forEach((point) => {
          storyContext.save();
          storyContext.globalAlpha = dataAlpha;
          storyContext.fillStyle = "#dce5e1";
          storyContext.font = '600 10px "Cascadia Mono", Consolas, monospace';
          storyContext.textAlign = "center";
          storyContext.fillText(point.label, point.x, axisBottom + 21);
          storyContext.fillStyle = point.color;
          storyContext.fillText(point.value.toFixed(2), point.x, point.y - 12);
          storyContext.restore();
        });
      }

      if (meanAlpha > 0.01) {
        const meanY = chart.yForValue(mean);
        storyContext.save();
        storyContext.globalAlpha = meanAlpha;
        storyContext.setLineDash([7, 5]);
        storyContext.strokeStyle = "#b7a3ff";
        storyContext.lineWidth = 1;
        storyContext.beginPath();
        storyContext.moveTo(chart.left, meanY);
        storyContext.lineTo(chart.left + chart.plotWidth, meanY);
        storyContext.stroke();
        storyContext.setLineDash([]);
        storyContext.fillStyle = "#b7a3ff";
        storyContext.font = '600 9px "Cascadia Mono", Consolas, monospace';
        storyContext.fillText(
          `RUN MEAN ${mean.toFixed(2)} dB`,
          chart.left + chart.plotWidth * 0.43,
          meanY - 9,
        );
        storyContext.restore();
      }

      if (smoothProgress > 0.86) {
        const width = chart.compact ? 55 : 78;
        const x = chart.left + chart.plotWidth - width;
        const y = chart.top + 13;
        storyContext.save();
        storyContext.globalAlpha = smoothstep(0.86, 0.96, smoothProgress);
        storyContext.setLineDash([5, 5]);
        storyContext.strokeStyle = "#ff896c";
        storyContext.strokeRect(x, y, width, 40);
        storyContext.fillStyle = "#ff896c";
        storyContext.font = '7px "Cascadia Mono", Consolas, monospace';
        storyContext.fillText("NEXT?", x + 7, y + 14);
        storyContext.font = '17px "Segoe UI", sans-serif';
        storyContext.fillText("?", x + width * 0.48, y + 32);
        storyContext.restore();
      }

      if (storyVisible && !document.hidden && !reducedMotion) {
        storyFrame = requestAnimationFrame(drawStory);
      } else {
        storyFrame = null;
      }
    };

    const updateStoryScroll = () => {
      const rect = storyScrolly.getBoundingClientRect();
      const travel = Math.max(1, storyScrolly.offsetHeight - window.innerHeight);
      targetProgress = clamp(-rect.top / travel);
      if (reducedMotion) {
        smoothProgress = targetProgress;
        drawStory(performance.now());
      } else if (storyVisible && !storyFrame) {
        storyFrame = requestAnimationFrame(drawStory);
      }
    };

    buildFallbackDotField();
    layoutStoryCanvas();
    setStoryStep(0);
    updateStoryScroll();
    const storyResizeObserver = new ResizeObserver(layoutStoryCanvas);
    storyResizeObserver.observe(storyCanvas);
    window.addEventListener("scroll", updateStoryScroll, { passive: true });

    sourceImage.decoding = "async";
    sourceImage.onload = () => {
      imageReady = true;
      buildDotField();
      if (reducedMotion) drawStory(performance.now());
    };
    sourceImage.onerror = () => {
      imageReady = false;
      buildFallbackDotField();
    };
    sourceImage.src = new URL("./assets/adc-slice.png", document.baseURI).href;

    if ("IntersectionObserver" in window) {
      const storyVisibilityObserver = new IntersectionObserver(
        (entries) => {
          storyVisible = entries[0].isIntersecting;
          if (storyVisible && !storyFrame) {
            lastStoryTime = 0;
            storyFrame = requestAnimationFrame(drawStory);
          }
        },
        { rootMargin: "200px 0px" },
      );
      storyVisibilityObserver.observe(storySection);
    }

    if (reducedMotion) {
      smoothProgress = targetProgress;
      storyFrame = null;
      drawStory(performance.now());
    } else if (storyVisible) {
      storyFrame = requestAnimationFrame(drawStory);
    }
  }
})();
