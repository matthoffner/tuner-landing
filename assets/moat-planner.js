(() => {
  "use strict";

  const root = document.querySelector("[data-moat-planner]");
  if (!root) return;

  const form = root.querySelector("[data-planner-form]");
  const result = root.querySelector("[data-planner-result]");
  const steps = Array.from(root.querySelectorAll("[data-planner-step]"));
  const backButton = root.querySelector("[data-planner-back]");
  const nextButton = root.querySelector("[data-planner-next]");
  const generateButton = root.querySelector("[data-planner-generate]");
  const cancelButton = root.querySelector("[data-planner-cancel]");
  const progress = root.querySelector("[data-planner-progress]");
  const stepCount = root.querySelector("[data-planner-step-count]");
  const errorNode = root.querySelector("[data-planner-error]");
  const generationStatus = root.querySelector("[data-planner-generation-status]");
  const memoryGuidance = root.querySelector("[data-memory-guidance]");
  const loadExampleButton = document.querySelector("[data-planner-example]");
  const editButton = root.querySelector("[data-plan-edit]");
  const copyButton = root.querySelector("[data-plan-copy]");
  const downloadButton = root.querySelector("[data-plan-download]");
  const actionStatus = root.querySelector("[data-plan-action-status]");

  let activeStep = 0;
  let currentPayload = null;
  let generating = false;
  let activeController = null;
  let cancelledByUser = false;

  function checkedValue(name) {
    const field = form.querySelector(`[name="${name}"]:checked`);
    return field ? field.value : "";
  }

  function checkedValues(name) {
    return Array.from(form.querySelectorAll(`[name="${name}"]:checked`)).map((field) => (
      field.value
    ));
  }

  function field(name) {
    return form.elements.namedItem(name);
  }

  function setRadio(name, value) {
    const control = form.querySelector(`[name="${name}"][value="${value}"]`);
    if (control) control.checked = true;
  }

  function firstField(name) {
    return form.querySelector(`[name="${name}"]`);
  }

  function clearValidationState() {
    form.querySelectorAll('[aria-invalid="true"]').forEach((control) => {
      control.removeAttribute("aria-invalid");
      control.removeAttribute("aria-describedby");
    });
  }

  function setStep(nextStep, { focus = true } = {}) {
    activeStep = Math.max(0, Math.min(steps.length - 1, nextStep));
    steps.forEach((step, index) => {
      step.hidden = index !== activeStep;
    });
    const completed = ((activeStep + 1) / steps.length) * 100;
    progress.style.width = `${completed}%`;
    progress.parentElement.setAttribute("aria-valuenow", String(activeStep + 1));
    stepCount.textContent = `Step ${activeStep + 1} of ${steps.length}`;
    backButton.hidden = activeStep === 0;
    nextButton.hidden = activeStep === steps.length - 1;
    generateButton.hidden = activeStep !== steps.length - 1;
    errorNode.textContent = "";
    clearValidationState();
    if (focus) {
      const legend = steps[activeStep].querySelector("legend");
      if (legend) window.requestAnimationFrame(() => legend.focus());
    }
  }

  function showError(message, control) {
    errorNode.textContent = message;
    if (control) {
      const controls = control.name
        ? form.querySelectorAll(`[name="${control.name}"]`)
        : [control];
      controls.forEach((item) => {
        item.setAttribute("aria-invalid", "true");
        item.setAttribute("aria-describedby", "planner-error");
      });
      if (typeof control.focus === "function") control.focus();
    }
    return false;
  }

  function validateStep(index) {
    clearValidationState();
    if (index === 0) {
      if (!checkedValue("hardwareIntent")) {
        return showError("Choose whether this is an existing machine or a memory tier you are planning.", firstField("hardwareIntent"));
      }
      if (!checkedValue("platform")) {
        return showError("Choose a hardware type. “Not sure” is a valid answer.", firstField("platform"));
      }
      if (!checkedValue("memoryGb")) {
        return showError("Choose the memory Automoat may use, or ask it to recommend a tier.", firstField("memoryGb"));
      }
    }
    if (index === 1) {
      if (!checkedValue("schedule")) {
        return showError("Choose when Automoat may run.", firstField("schedule"));
      }
      const hours = Number(field("hoursPerDay").value);
      if (!Number.isInteger(hours) || hours < 1 || hours > 24) {
        return showError("Available hours must be a whole number from 1 to 24.", field("hoursPerDay"));
      }
      if (!checkedValue("resourceCeiling")) {
        return showError("Choose a resource posture.", firstField("resourceCeiling"));
      }
    }
    if (index === 2) {
      if (!checkedValue("moatMode")) {
        return showError("Tell us whether to shape your idea or suggest one.", firstField("moatMode"));
      }
      const idea = field("idea").value.trim();
      if (checkedValue("moatMode") === "shape" && idea.length < 8) {
        return showError("Describe the recurring job in at least a few words.", field("idea"));
      }
    }
    if (index === 3) {
      for (const [name, message] of [
        ["goal", "Choose what should improve."],
        ["network", "Choose a network boundary."],
        ["autonomy", "Choose an autonomy level."],
        ["verifier", "Choose the strongest available verifier."],
      ]) {
        if (!field(name).value) return showError(message, field(name));
      }
    }
    errorNode.textContent = "";
    return true;
  }

  function collectAnswers() {
    const memoryValue = checkedValue("memoryGb");
    return {
      hardwareIntent: checkedValue("hardwareIntent"),
      platform: checkedValue("platform"),
      memoryGb: memoryValue === "recommend" ? "recommend" : Number(memoryValue),
      schedule: checkedValue("schedule"),
      hoursPerDay: Number(field("hoursPerDay").value),
      resourceCeiling: Number(checkedValue("resourceCeiling")),
      workCategories: checkedValues("workCategories"),
      moatMode: checkedValue("moatMode"),
      idea: checkedValue("moatMode") === "shape" ? field("idea").value.trim() : "",
      privateContext: field("privateContext").value.trim(),
      usefulResult: field("usefulResult").value.trim(),
      goal: field("goal").value,
      network: field("network").value,
      autonomy: field("autonomy").value,
      verifier: field("verifier").value,
    };
  }

  const STARTER_MOATS = {
    code: [
      "Nightly codebase caretaker",
      "Turn failing checks and explicit backlog signals into one tested patch or investigation.",
      "Repository history, accepted patches, tests, and maintainer corrections.",
      "A tested patch, regression test, or evidence-backed investigation.",
      "Tests, diff scope, and human acceptance.",
    ],
    research: [
      "Private research distiller",
      "Turn saved sources and open questions into concise briefs and a reusable claim ledger.",
      "Your source library, prior conclusions, and rejected claims.",
      "A cited brief with structured claims and unresolved questions.",
      "Citation coverage and accepted edits.",
    ],
    documents: [
      "Private knowledge compactor",
      "Turn changing local documents into searchable decisions and held-out questions.",
      "Internal terminology, decisions, and corrections.",
      "A local index, decision digest, and retrieval task pack.",
      "Schema checks and answer-grounding tests.",
    ],
    operations: [
      "Workflow exception finder",
      "Review recurring records, surface exceptions, and propose the next bounded action.",
      "Historical decisions, outcomes, corrections, and edge cases.",
      "A ranked exception queue with evidence and proposed actions.",
      "Known outcomes and operator acceptance.",
    ],
    creative: [
      "Local taste memory",
      "Generate and rank drafts using your own revision history.",
      "Accepted work, rejected variants, and revision notes.",
      "A small set of ranked drafts with selection rationale.",
      "Accepted edits and rubric scores.",
    ],
    personal: [
      "Personal workflow gardener",
      "Turn recurring local chores and notes into drafts and next actions for review.",
      "Your routines, preferences, outcomes, and corrections.",
      "A review queue of proposed drafts and next actions.",
      "Manual approval and completion outcomes.",
    ],
    performance: [
      "Local token yield lab",
      "Test which model, prompt, context, and task combinations create verified value per token.",
      "Accepted and rejected attempts, task packs, and machine-specific receipts.",
      "A promoted routing policy plus immutable run receipts.",
      "Held-out quality, token usage, latency, and regression gates.",
    ],
  };

  function clientMemoryProfile(answers) {
    let memory = typeof answers.memoryGb === "number" ? answers.memoryGb : null;
    if (!memory) {
      memory = answers.goal === "performance"
        || answers.workCategories.includes("code")
        || answers.workCategories.includes("creative")
        ? 64
        : 32;
    }
    const tiers = [8, 16, 24, 32, 48, 64, 96, 128];
    const profiles = {
      8: ["1–3B quantized", "one small job", "4K–8K after calibration"],
      16: ["7–8B quantized", "one job at a time", "8K–16K after calibration"],
      24: ["8–14B quantized", "one job at a time", "8K–24K after calibration"],
      32: ["14B quantized", "one main job", "16K–32K after calibration"],
      48: ["14–27B quantized", "one main or two small jobs", "16K–32K after calibration"],
      64: ["27–32B quantized", "one large or two small jobs", "up to 32K after calibration"],
      96: ["32B with headroom or a 70B test", "one large or two medium jobs", "32K–64K after calibration"],
      128: ["70B quantized or parallel 14–32B", "one 70B or several bounded jobs", "up to 64K after calibration"],
    };
    const index = tiers.indexOf(memory);
    const memoryKind = answers.platform === "apple_silicon"
      ? "unified memory"
      : answers.platform === "nvidia"
        ? "GPU VRAM"
        : answers.platform === "cpu_other"
          ? "system RAM"
          : "memory";
    return {
      intent: answers.hardwareIntent,
      platform: answers.platform,
      memory_kind: memoryKind,
      selected_memory_gb: typeof answers.memoryGb === "number" ? answers.memoryGb : null,
      recommended_memory_gb: memory,
      minimum_memory_gb: tiers[Math.max(0, index - 1)],
      headroom_memory_gb: tiers[Math.min(tiers.length - 1, index + 1)],
      model_band: profiles[memory][0],
      concurrency: profiles[memory][1],
      context_window: profiles[memory][2],
      recommendation_reason: typeof answers.memoryGb === "number"
        ? "Treat this as a ceiling and benchmark the real machine before scaling."
        : "This is a balanced starting point; let the first local receipt decide whether to move down or up.",
      benchmark_required: true,
      available_hours_per_day: answers.hoursPerDay,
      resource_ceiling_percent: answers.resourceCeiling,
      schedule: answers.schedule,
    };
  }

  function clientFallback(answers, { hostedRequestAttempted = true } = {}) {
    const categoryKeys = [...answers.workCategories];
    if (answers.goal === "performance") categoryKeys.unshift("performance");
    if (!categoryKeys.length) categoryKeys.push("performance");
    for (const key of ["code", "operations", "documents"]) {
      if (!categoryKeys.includes(key)) categoryKeys.push(key);
    }
    const suggestions = categoryKeys.slice(0, 3).map((key) => STARTER_MOATS[key]);
    const chosen = suggestions[0];
    const userIdea = answers.moatMode === "shape";
    const metricByGoal = {
      time: "accepted artifacts and review minutes saved per million local tokens",
      quality: "accepted artifacts without regression per million local tokens",
      revenue: "accepted revenue-supporting actions per million local tokens",
      knowledge: "held-out retrieval quality per million local tokens",
      performance: "held-out task lift per million local tokens",
    };
    const moat = {
      origin: userIdea ? "user" : "suggested",
      title: userIdea ? "Your compounding local-work loop" : chosen[0],
      recurring_job: userIdea ? answers.idea : chosen[1],
      private_context: answers.privateContext || (userIdea
        ? "Your local examples, corrections, and outcomes."
        : chosen[2]),
      output_artifact: answers.usefulResult || (userIdea
        ? "One reviewable artifact per bounded run."
        : chosen[3]),
      verifier: chosen[4],
      feedback_signal: "Record accepted, rejected, and edited results for the next run.",
      success_metric: metricByGoal[answers.goal],
    };
    const allocation = answers.goal === "performance"
      ? [["Useful work", 35], ["Verification", 35], ["Context curation", 10], ["Exploration", 20]]
      : [["Useful work", 55], ["Verification", 20], ["Context curation", 15], ["Exploration", 10]];
    return {
      schema_version: "automoat-plan-v1",
      title: `${moat.title}: a bounded local token plan`,
      summary: "Start with measurable jobs, spend more only after they pass, and stop when no verifiable work remains.",
      hardware: clientMemoryProfile(answers),
      moat,
      alternative_ideas: suggestions.slice(1).map((item) => ({
        title: item[0], recurring_job: item[1], verifier: item[4],
      })),
      policy: {
        network: answers.network,
        autonomy: answers.autonomy,
        primary_verifier: answers.verifier.replaceAll("_", " "),
      },
      token_plan: {
        calibration_minutes: 15,
        daily_budget_after_calibration: null,
        budget_rule: "Convert measured tokens per second and available hours into a daily cap after the first local receipt.",
        allocation: allocation.map(([label, percent]) => ({
          label,
          percent,
          purpose: label === "Useful work"
            ? "Create ranked artifacts from explicit local signals."
            : `Keep ${label.toLowerCase()} bounded and measurable.`,
        })),
      },
      queue: [
        {
          task: "Measure the local baseline",
          artifact: "A content-free run receipt for one small immutable task pack.",
          verifier: "Complete usage, wall time, hardware provenance, and strict task score.",
          max_attempts: 1,
        },
        {
          task: `Run one bounded ${moat.title.toLowerCase()} job`,
          artifact: moat.output_artifact,
          verifier: moat.verifier,
          max_attempts: 2,
        },
        {
          task: "Compare generic versus private context",
          artifact: "A digest-matched baseline-versus-candidate report.",
          verifier: "Promote only after held-out quality improves.",
          max_attempts: 2,
        },
      ],
      scorecard: {
        primary_metric: moat.success_metric,
        promotion_gate: "Require the quality floor first; among passing candidates, prefer fewer uncached tokens and lower latency.",
        stop_rule: "Unused capacity is better than unverified activity. Stop when the queue has no measurable value.",
      },
      first_week: [
        "Run a 15-minute local calibration and save the receipt.",
        "Freeze 10–20 representative tasks and their verifiers.",
        "Run a generic baseline and one private-context candidate on the same digest.",
        "Review failures, record corrections, and promote or pause based on verified value per token.",
      ],
      privacy_note: hostedRequestAttempted
        ? "This starter contains no LLM-generated content. A hosted request may have been attempted before fallback; no local files or local model outputs were read."
        : "You chose the browser-only starter. No questionnaire answers, local files, or local model outputs were sent to a hosted planner.",
    };
  }

  function safeString(value, fallback = "") {
    return typeof value === "string" && value.trim() ? value.trim() : fallback;
  }

  function setText(selector, value, fallback = "—") {
    const node = root.querySelector(selector);
    if (node) node.textContent = safeString(value, fallback);
  }

  function clearAndAppend(list, items, builder) {
    list.replaceChildren();
    items.forEach((item, index) => list.append(builder(item, index)));
  }

  function planItems(value, maximum) {
    return Array.isArray(value) ? value.slice(0, maximum) : [];
  }

  function renderPlan(payload) {
    const plan = payload.plan;
    currentPayload = payload;
    setText("[data-plan-title]", plan.title, "Your local token operating plan");
    setText("[data-plan-summary]", plan.summary);
    setText("[data-plan-notice]", payload.notice);
    const inferenceScope = payload.planner && payload.planner.inference_scope;
    const modeLabel = payload.generated_by === "llm"
      ? "AI-tailored · planning only"
      : inferenceScope === "browser_only" || inferenceScope === "browser_to_server_only"
        ? "Private starter · no model call"
        : "Rule-based starter · hosted attempt failed";
    setText("[data-plan-mode]", modeLabel);

    const hardware = plan.hardware || {};
    setText("[data-plan-memory]", `${hardware.recommended_memory_gb || "?"} GB`);
    setText("[data-plan-model]", hardware.model_band);
    setText("[data-plan-concurrency]", hardware.concurrency);
    setText("[data-plan-context]", hardware.context_window);
    setText("[data-plan-hardware-reason]", hardware.recommendation_reason);
    const selectedMemory = hardware.selected_memory_gb
      ? `${hardware.selected_memory_gb} GB ${hardware.memory_kind || "memory"} selected`
      : "Memory tier suggested from the work profile";
    setText(
      "[data-plan-memory-range]",
      `${selectedMemory} · ${hardware.minimum_memory_gb || "?"} GB minimum · ${hardware.headroom_memory_gb || "?"} GB headroom`,
    );

    const scheduleLabels = {
      overnight: "Overnight",
      idle: "Whenever the machine is idle",
      quiet: "While you work, under a quiet limit",
      custom: "Custom schedule",
    };
    const networkLabels = {
      loopback_only: "Local and loopback only",
      local_plus_readonly_web: "Local inference with read-only web research",
      remote_opt_in: "Explicit remote fallback allowed",
    };
    const autonomyLabels = {
      recommend: "Recommend only",
      draft: "Create drafts and patches",
      bounded_execute: "Execute bounded changes after checks",
    };
    const policy = plan.policy || {};
    const calibration = plan.token_plan && plan.token_plan.calibration_minutes;
    setText("[data-plan-boundary-schedule]", scheduleLabels[hardware.schedule] || hardware.schedule);
    setText(
      "[data-plan-boundary-capacity]",
      `${hardware.available_hours_per_day || "?"} h/day · ${hardware.resource_ceiling_percent || "?"}% ceiling · ${calibration || 15} min calibration`,
    );
    setText("[data-plan-boundary-network]", networkLabels[policy.network] || policy.network);
    setText("[data-plan-boundary-autonomy]", autonomyLabels[policy.autonomy] || policy.autonomy);
    setText("[data-plan-boundary-verifier]", policy.primary_verifier);

    const moat = plan.moat || {};
    setText("[data-plan-moat-title]", moat.title);
    setText("[data-plan-moat-job]", moat.recurring_job);
    setText("[data-plan-moat-context]", moat.private_context);
    setText("[data-plan-moat-artifact]", moat.output_artifact);
    setText("[data-plan-moat-verifier]", moat.verifier);
    setText("[data-plan-metric]", moat.success_metric);

    const allocationList = root.querySelector("[data-plan-allocation]");
    clearAndAppend(allocationList, planItems(plan.token_plan && plan.token_plan.allocation, 4), (item) => {
      const row = document.createElement("li");
      row.className = "planner-allocation-item";
      const label = document.createElement("span");
      label.className = "planner-allocation-label";
      label.textContent = safeString(item.label, "Allocation");
      const percent = document.createElement("span");
      percent.className = "planner-allocation-percent";
      const boundedPercent = Math.max(0, Math.min(100, Number(item.percent) || 0));
      percent.textContent = `${boundedPercent}%`;
      const track = document.createElement("span");
      track.className = "planner-allocation-track";
      const fill = document.createElement("span");
      fill.className = "planner-allocation-fill";
      fill.style.setProperty("--allocation", `${boundedPercent}%`);
      track.append(fill);
      const purpose = document.createElement("span");
      purpose.className = "planner-allocation-purpose";
      purpose.textContent = safeString(item.purpose);
      row.append(label, percent, track, purpose);
      return row;
    });

    const queueList = root.querySelector("[data-plan-queue]");
    clearAndAppend(queueList, planItems(plan.queue, 3), (item, index) => {
      const row = document.createElement("li");
      row.className = "planner-queue-item";
      const title = document.createElement("strong");
      title.textContent = `${index + 1}. ${safeString(item.task, "Bounded task")}`;
      const artifact = document.createElement("span");
      artifact.textContent = `${safeString(item.artifact)} · Verify: ${safeString(item.verifier)}`;
      row.append(title, artifact);
      return row;
    });

    const weekList = root.querySelector("[data-plan-week]");
    clearAndAppend(weekList, planItems(plan.first_week, 7), (item) => {
      const row = document.createElement("li");
      row.textContent = safeString(item);
      return row;
    });

    const alternatives = planItems(plan.alternative_ideas, 2);
    const alternativesCard = root.querySelector("[data-plan-alternatives-card]");
    alternativesCard.hidden = alternatives.length === 0;
    const alternativesList = root.querySelector("[data-plan-alternatives]");
    clearAndAppend(alternativesList, alternatives, (item) => {
      const row = document.createElement("li");
      row.className = "planner-alternative-item";
      const title = document.createElement("strong");
      title.textContent = safeString(item.title, "Alternative moat");
      const copy = document.createElement("span");
      copy.textContent = `${safeString(item.recurring_job)} · Verify: ${safeString(item.verifier)}`;
      row.append(title, copy);
      return row;
    });

    const scorecard = plan.scorecard || {};
    setText("[data-plan-scorecard-metric]", scorecard.primary_metric || moat.success_metric);
    setText("[data-plan-promotion]", scorecard.promotion_gate);
    setText("[data-plan-stop]", scorecard.stop_rule);
    setText("[data-plan-privacy]", plan.privacy_note);

    form.hidden = true;
    result.hidden = false;
    actionStatus.textContent = "";
    result.focus();
    root.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function setGenerating(value) {
    generating = value;
    form.setAttribute("aria-busy", String(value));
    form.querySelectorAll("input, textarea, select").forEach((control) => {
      control.disabled = value;
    });
    backButton.disabled = value;
    nextButton.disabled = value;
    generateButton.disabled = value;
    generationStatus.hidden = !value;
    cancelButton.hidden = !value;
    generateButton.textContent = value ? "Building your plan…" : "Generate my operating plan";
    if (!value) syncIdeaMode();
  }

  async function requestPlan(answers) {
    const controller = new AbortController();
    activeController = controller;
    const timeout = window.setTimeout(() => controller.abort(), 22_000);
    try {
      const response = await fetch("/api/moat-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        cache: "no-store",
        body: JSON.stringify(answers),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`planner returned ${response.status}`);
      const payload = await response.json();
      if (!payload || typeof payload !== "object" || !payload.plan) {
        throw new Error("planner returned an invalid plan");
      }
      return payload;
    } finally {
      window.clearTimeout(timeout);
      if (activeController === controller) activeController = null;
    }
  }

  async function generatePlan(event) {
    event.preventDefault();
    if (generating) return;
    if (activeStep < steps.length - 1) {
      if (validateStep(activeStep)) setStep(activeStep + 1);
      return;
    }
    if (!validateStep(3)) return;
    const answers = collectAnswers();
    if (!field("useHostedPlanner").checked) {
      renderPlan({
        generated_by: "fallback",
        fallback_reason: "hosted_planner_opted_out",
        planner: { provider: "deterministic_starter", model: null, inference_scope: "browser_only", usage: null },
        notice: "You chose a browser-only rule-based starter, so no questionnaire answers were sent to a hosted model.",
        plan: clientFallback(answers, { hostedRequestAttempted: false }),
      });
      return;
    }
    cancelledByUser = false;
    setGenerating(true);
    errorNode.textContent = "";
    try {
      const payload = await requestPlan(answers);
      renderPlan(payload);
    } catch (_error) {
      if (cancelledByUser) {
        errorNode.textContent = "Generation cancelled. Your answers are still here.";
        return;
      }
      renderPlan({
        generated_by: "fallback",
        fallback_reason: "planner_unreachable",
        planner: { provider: "deterministic_starter", model: null, inference_scope: "remote_attempted", usage: null },
        notice: "The hosted planner did not return a plan, so this starter was generated in your browser. The hosted request may have been attempted.",
        plan: clientFallback(answers, { hostedRequestAttempted: true }),
      });
    } finally {
      setGenerating(false);
    }
  }

  function syncIdeaMode() {
    const shaping = checkedValue("moatMode") === "shape";
    const ideaWrap = root.querySelector("[data-idea-field]");
    ideaWrap.hidden = !shaping;
    field("idea").required = shaping;
    field("idea").disabled = generating || !shaping;
  }

  function syncMemoryGuidance() {
    const platform = checkedValue("platform");
    const guidance = {
      apple_silicon: "Choose unified memory available to the whole system. Model fit remains provisional until a local calibration.",
      nvidia: "Choose usable GPU VRAM here; system RAM still matters separately. Model fit remains provisional until a local calibration.",
      cpu_other: "Choose system RAM available to inference. CPU speed and memory bandwidth still require a local calibration.",
      unknown: "Choose a provisional memory ceiling. Automoat will identify the memory kind and benchmark the real machine before scaling.",
    };
    memoryGuidance.textContent = guidance[platform] || "Choose the memory available to inference. Automoat will benchmark the actual machine before promising throughput.";
  }

  function loadExample() {
    result.hidden = true;
    form.hidden = false;
    setRadio("hardwareIntent", "existing");
    setRadio("platform", "apple_silicon");
    setRadio("memoryGb", "32");
    setRadio("schedule", "overnight");
    field("hoursPerDay").value = "8";
    setRadio("resourceCeiling", "60");
    form.querySelectorAll('[name="workCategories"]').forEach((control) => {
      control.checked = control.value === "code" || control.value === "documents";
    });
    setRadio("moatMode", "suggest");
    field("idea").value = "";
    field("useHostedPlanner").checked = true;
    field("privateContext").value = "Accepted patches, test history, and project decisions";
    field("usefulResult").value = "One tested patch or useful investigation by morning";
    field("goal").value = "performance";
    field("network").value = "loopback_only";
    field("autonomy").value = "draft";
    field("verifier").value = "tests";
    syncIdeaMode();
    setStep(3);
    root.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  backButton.addEventListener("click", () => setStep(activeStep - 1));
  nextButton.addEventListener("click", () => {
    if (validateStep(activeStep)) setStep(activeStep + 1);
  });
  cancelButton.addEventListener("click", () => {
    cancelledByUser = true;
    if (activeController) activeController.abort();
  });
  form.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.target.tagName === "TEXTAREA" || activeStep === steps.length - 1) return;
    event.preventDefault();
    if (validateStep(activeStep)) setStep(activeStep + 1);
  });
  form.addEventListener("submit", generatePlan);
  form.querySelectorAll('[name="moatMode"]').forEach((control) => {
    control.addEventListener("change", syncIdeaMode);
  });
  form.querySelectorAll('[name="platform"]').forEach((control) => {
    control.addEventListener("change", syncMemoryGuidance);
  });
  if (loadExampleButton) loadExampleButton.addEventListener("click", loadExample);
  editButton.addEventListener("click", () => {
    result.hidden = true;
    form.hidden = false;
    setStep(2);
  });
  copyButton.addEventListener("click", async () => {
    if (!currentPayload) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(currentPayload.plan, null, 2));
      actionStatus.textContent = "Plan JSON copied.";
    } catch (_error) {
      actionStatus.textContent = "Copy was blocked by the browser; use Download plan.json instead.";
    }
  });
  downloadButton.addEventListener("click", () => {
    if (!currentPayload) return;
    const blob = new Blob([`${JSON.stringify(currentPayload.plan, null, 2)}\n`], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "automoat-plan.json";
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    actionStatus.textContent = "Downloaded automoat-plan.json.";
  });

  syncIdeaMode();
  syncMemoryGuidance();
  setStep(0, { focus: false });
})();
