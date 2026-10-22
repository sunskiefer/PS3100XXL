// SPDX-License-Identifier: GPL-3.0-or-later
// PS3100XXL engine tests (x86, ASan/UBSan): test/run_tests.sh
// The patch bay and zoom logic the skin depends on, the state, and the sound: every control swept, every cable
// patched, every waveform, pitch, polyphony and CPU.
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <string>
extern "C" {
#include "engine.h"
}
#include "param_ids.h"

static int fails = 0, checks = 0;
#define CHECK(cond, ...)                                  \
  do {                                                    \
    checks++;                                             \
    if (!(cond)) { fails++; printf("FAIL "); printf(__VA_ARGS__); printf("\n"); } \
  } while (0)

static const mpc_engine_t *E;

static std::string get(void *s, const char *k) {
  char buf[8192];
  int n = E->get_param(s, k, buf, sizeof buf);
  return n > 0 ? std::string(buf) : std::string();
}
static int geti(void *s, const char *k) { return atoi(get(s, k).c_str()); }
static float getf(void *s, const char *k) { return (float)atof(get(s, k).c_str()); }
static void set(void *s, const char *k, const char *v) { E->set_param(s, k, v); }
static void setf(void *s, const char *k, float v) { char b[32]; snprintf(b, sizeof b, "%g", v); E->set_param(s, k, b); }
static void tap(void *s, const char *jack) { std::string k = std::string("tap_") + jack; set(s, k.c_str(), "1"); }
static void note(void *s, int n, int v) { uint8_t m[3] = {(uint8_t)(v ? 0x90 : 0x80), (uint8_t)n, (uint8_t)(v ? v : 0)}; E->midi(s, m, 3); }

struct Stats { double rms; int peak; bool bad; int crossings; };
static Stats render(void *s, int blocks) {
  int16_t buf[256];
  Stats st = {0, 0, false, 0};
  double acc = 0;
  int last = 0;
  long n = 0;
  for (int b = 0; b < blocks; b++) {
    E->render(s, buf, 128);
    for (int i = 0; i < 128; i++) {
      int l = buf[i * 2];
      acc += (double)l * l;
      if (abs(l) > st.peak) st.peak = abs(l);
      if ((l >= 0) != (last >= 0)) st.crossings++;
      last = l;
      n++;
    }
  }
  st.rms = sqrt(acc / n) / 32768.0;
  return st;
}

static int out_index(const char *k) { for (int i = 0; i < N_OUTS; i++) if (!strcmp(OUT_KEY[i], k)) return i; return -1; }
static int in_index(const char *k) { for (int i = 0; i < N_INS; i++) if (!strcmp(IN_KEY[i], k)) return i; return -1; }

int main() {
  E = mpc_engine();
  void *s = E->create(nullptr);

  // ---- views and navigation
  CHECK(geti(s, "view") == V_OVERVIEW, "starts on the overview");
  set(s, "go_lp", "1");
  CHECK(geti(s, "view") == V_LP, "go_lp zooms in (%d)", geti(s, "view"));
  set(s, "nav_next", "1");
  CHECK(geti(s, "view") == V_EM, "next steps to the envelope");
  set(s, "nav_prev", "1"); set(s, "nav_prev", "1");
  CHECK(geti(s, "view") == V_SG, "prev twice: signal gen");
  set(s, "nav_prev", "1");
  CHECK(geti(s, "view") == N_VIEWS - 1, "prev wraps to the last section");
  set(s, "nav_zoom", "1");
  CHECK(geti(s, "view") == V_OVERVIEW, "OVERVIEW returns");
  set(s, "go_lp", "0");
  CHECK(geti(s, "view") == V_OVERVIEW, "a trigger's release (0) does nothing");

  // ---- Q-Links follow the view
  set(s, "go_lp", "1");
  CHECK(get(s, "ql1_name") == "Cutoff", "ql1 is Cutoff on the lowpass page ('%s')", get(s, "ql1_name").c_str());
  setf(s, "ql1", 0.25f);
  CHECK(fabsf(getf(s, "lp_cutoff") - 2.5f) < 0.01f, "ql1 drives the cutoff (%g)", getf(s, "lp_cutoff"));
  setf(s, "lp_cutoff", 8.0f);
  CHECK(fabsf(getf(s, "ql1") - 0.8f) < 0.01f, "the Q-Link follows the knob (%g)", getf(s, "ql1"));
  set(s, "go_patch", "1");
  CHECK(get(s, "ql1_name") == "-", "no Q-Link targets on the patch page");
  for (int v = 0; v < N_VIEWS; v++)
    for (int i = 0; i < 16; i++) {
      int t = VIEW_QLINKS[v][i];
      CHECK(t < N_CONTROLS, "Q-Link targets are sound controls");
    }

  // ---- patching
  unsigned rev0 = (unsigned)geti(s, "display_rev");
  tap(s, "geg");
  CHECK(geti(s, "held") == 1 + out_index("geg"), "tapping an output holds it");
  CHECK((unsigned)geti(s, "display_rev") != rev0, "a tap bumps display_rev");
  tap(s, "sg_frq");
  CHECK(geti(s, "held") == 0, "an input tap completes the cable");
  CHECK(geti(s, "cab_geg") == 1 + IN_TYPED[in_index("sg_frq")], "cab_geg shows the patch-page cable (%d)", geti(s, "cab_geg"));
  set(s, "nav_zoom", "1");
  CHECK(geti(s, "cab_geg") == 1 + N_CV_INS + IN_TYPED[in_index("sg_frq")], "and the overview copy on the overview");
  set(s, "go_lp", "1");
  CHECK(geti(s, "cab_geg") == 0, "no cable pictures on other pages");
  CHECK(geti(s, "held") == 0, "no held ring off the patch page");
  set(s, "go_patch", "1");
  tap(s, "mg1"); tap(s, "sg_frq");
  CHECK(geti(s, "cab_geg") == 0 && geti(s, "cab_mg1") == 1 + IN_TYPED[in_index("sg_frq")], "one cable per input: MG1 replaces GEG");
  tap(s, "mg1");
  CHECK(geti(s, "cab_mg1") == 0 && geti(s, "held") == 0, "tapping a patched output unplugs it");
  tap(s, "trg1"); tap(s, "sg_frq");
  CHECK(geti(s, "cab_trg1") == 0, "a trigger can't go into a voltage input");
  CHECK(get(s, "patch_info").find("trigger") != std::string::npos, "and the info line says why");
  tap(s, "geg_trg");
  CHECK(geti(s, "cab_trg1") == 1 + IN_TYPED[in_index("geg_trg")], "trigger to trigger works");
  tap(s, "vp1"); tap(s, "vp1");
  CHECK(geti(s, "held") == 0, "tapping the held output again lets it go");

  // ---- state
  setf(s, "lp_peak", 7.5f);
  set(s, "sg_wave", "4");
  tap(s, "mw"); tap(s, "mg_amt");
  std::string st = get(s, "state");
  CHECK(st.size() > 100 && st.size() < 8000, "state fits the wrapper's chunk (%d bytes)", (int)st.size());
  void *s2 = E->create(nullptr);
  set(s2, "state", st.c_str());
  CHECK(fabsf(getf(s2, "lp_peak") - 7.5f) < 1e-4f && geti(s2, "sg_wave") == 4, "controls restore");
  set(s2, "go_patch", "1");
  CHECK(geti(s2, "cab_mw") == 1 + IN_TYPED[in_index("mg_amt")] && geti(s2, "cab_trg1") == 1 + IN_TYPED[in_index("geg_trg")],
        "cables restore");
  E->destroy(s2);

  // ---- temperament
  set(s, "temperament", "10");   // Kirnberger III
  CHECK(geti(s, "tune_e") == -14 && geti(s, "tune_c") == 0, "a template writes the tune knobs (E %d)", geti(s, "tune_e"));
  set(s, "temperament", "0");
  CHECK(geti(s, "tune_e") == 0, "Equal resets them");

  // ---- sound: pitch
  E->destroy(s);
  s = E->create(nullptr);
  set(s, "sg_wave", "1");
  setf(s, "lp_cutoff", 10);
  set(s, "ensemble", "0");
  setf(s, "final_vol", 7);
  note(s, 69, 100);
  render(s, 40);
  Stats a = render(s, 345);   // ~1 s
  CHECK(a.rms > 0.02 && !a.bad, "a note sounds (rms %.3f)", a.rms);
  CHECK(abs(a.crossings / 2 - 440) < 12, "A4 at 440 Hz (%d)", a.crossings / 2);
  set(s, "sg_octave", "2");
  render(s, 10);
  a = render(s, 345);
  CHECK(abs(a.crossings / 2 - 880) < 20, "4' an octave up (%d)", a.crossings / 2);
  note(s, 69, 0);
  set(s, "em_release", "0");
  render(s, 100);
  a = render(s, 50);
  CHECK(a.peak < 40, "damped release goes silent (%d)", a.peak);

  // ---- every waveform, every voice count, chords
  for (int w = 0; w < 6; w++) {
    char b[16]; snprintf(b, sizeof b, "%d", w);
    set(s, "sg_wave", b);
    note(s, 48, 100); note(s, 55, 100); note(s, 64, 100);
    a = render(s, 100);
    CHECK(a.rms > 0.01 && a.peak <= 32767, "waveform %d sounds (rms %.3f)", w, a.rms);
    note(s, 48, 0); note(s, 55, 0); note(s, 64, 0);
    render(s, 50);
  }

  // ---- every control swept with a chord held: no NaN, no overload past the limiter
  set(s, "em_release", "2");
  for (int p = 0; p < N_CONTROLS; p++) {
    if (p == P_TEMPERAMENT) continue;
    for (int k = 0; k <= 4; k++) {
      setf(s, P_KEY[p], P_MIN[p] + (P_MAX[p] - P_MIN[p]) * k / 4.0f);
      note(s, 40 + k * 7, 110);
      a = render(s, 8);
      CHECK(a.peak <= 32767 && a.rms == a.rms, "%s at %d/4", P_KEY[p], k);
    }
    setf(s, P_KEY[p], P_DEF[p]);
    for (int k = 0; k <= 4; k++) note(s, 40 + k * 7, 0);
  }

  // ---- every cable: each output into each input it can reach, with modulation turned up
  E->destroy(s);
  s = E->create(nullptr);
  set(s, "go_patch", "1");
  const char *ups[] = {"sg_fm_on", "lp_fm_on", "res_mg2", "am_mg1", "vca1_geg", "vca2_vp1"};
  for (const char *k : ups) set(s, k, "1");
  for (const char *k : {"sg_fm_mg1", "sg_fm_geg", "lp_fm_mg1", "lp_fm_geg", "res_int", "res_ext", "sg_pwm_int"}) setf(s, k, 7);
  set(s, "sg_wave", "5");
  int combos = 0;
  for (int o = 0; o < N_OUTS; o++)
    for (int j = 0; j < N_INS; j++) {
      if (OUT_TRIG[o] != IN_TRIG[j]) continue;
      tap(s, OUT_KEY[o]); tap(s, IN_KEY[j]);
      note(s, 60, 100);
      a = render(s, 6);
      note(s, 60, 0);
      CHECK(a.rms == a.rms && a.peak <= 32767, "cable %s -> %s", OUT_KEY[o], IN_KEY[j]);
      tap(s, OUT_KEY[o]);   // unplug
      combos++;
    }
  CHECK(combos == (N_OUTS - 9) * N_CV_INS + 9 * N_TRIG_INS, "all %d cables tried", combos);

  // ---- GEG LED shows only on its page
  set(s, "geg_trigger", "1");
  setf(s, "geg_attack", 0);
  set(s, "go_geg", "1");
  note(s, 60, 100);
  render(s, 20);
  CHECK(geti(s, "geg_led") == 1, "GEG LED lit while the GEG runs");
  set(s, "go_lp", "1");
  CHECK(geti(s, "geg_led") == 0, "and hidden on other pages");
  note(s, 60, 0);

  // ---- CPU: 48 voices, PWM, resonators, ensemble, all modulation
  E->destroy(s);
  s = E->create(nullptr);
  set(s, "voices", "5");
  set(s, "sg_wave", "5");
  setf(s, "res_int", 8);
  set(s, "sg_fm_on", "1"); setf(s, "sg_fm_mg1", 3);
  for (int n = 0; n < 48; n++) note(s, 36 + n, 100);
  render(s, 20);
  clock_t t0 = clock();
  a = render(s, 2000);
  double us = (double)(clock() - t0) / CLOCKS_PER_SEC * 1e6 / 2000;
  printf("info 48 voices: %.1f us per 128-frame block on this machine (budget 2902 us on the Force)\n", us);
  CHECK(a.rms > 0.01, "48 voices sound");
  E->destroy(s);

  printf("%s: %d checks, %d failed\n", fails ? "FAILED" : "PASSED", checks, fails);
  return fails ? 1 : 0;
}
