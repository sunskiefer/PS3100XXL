// SPDX-License-Identifier: GPL-3.0-or-later
// PS3100XXL -- a Korg PS-3100-style semi-modular polyphonic synthesizer for MPC OS (mpc-vst-plugins engine).
// Own DSP, written from the PS-3100's published architecture and the FB-3100 manual's description of it; no code
// from either. Signal path (as on the PS-3100):
//
//   per voice:  SG (oscillator) -> dynamic lowpass (2-pole) -> envelope modifier VCA -> keyboard balance
//   sum      -> [direct out]
//            -> resonators (3 peaks) -> amplitude modulator -> ensemble -> VCA 1 -> VCA 2 -> final -> limiter
//
// Modulation runs as a small "patch bay": every output (GEG, MGs, S/H, VPs, MIDI CVs, triggers ...) is computed each
// sample into out_v[]; an input reads the output a cable brings to it, or its hard-wired default when unpatched.
// One output feeds one input; the junctions copy a signal to two more outputs.
//
// The UI side lives here too: the zoom 'view', the jack taps, which cable picture each output shows, and 16 Q-Link
// knobs that follow the section on screen (see get/set of "ql<n>").
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <new>

extern "C" {
#include "engine.h"
}
#include "param_ids.h"
#include "denormals.h"
#include "limiter.h"

namespace {

const float SR = 44100.0f;
const float INV_SR = 1.0f / 44100.0f;
const float PI = 3.14159265358979f;
const int MAX_VOICES = 48;
const int VOICE_COUNTS[6] = {8, 12, 16, 24, 32, 48};
const int CTRL_EVERY = 8;   // per-voice pitch/filter coefficients are recomputed every 8 samples

inline float clampf(float x, float a, float b) { return x < a ? a : x > b ? b : x; }
inline float fast_exp2(float x) { return exp2f(x); }
// time knob 0..10 -> seconds, 1 ms .. 10 s (exponential, like the PS-3100's pots)
inline float knob_time(float v) { return 0.001f * powf(10.0f, clampf(v, 0, 10) * 0.4f); }
inline float rate_for(float seconds) { return 1.0f - expf(-1.0f / (fmaxf(seconds, 0.0005f) * SR)); }

// ---- small DSP pieces ---------------------------------------------------------------------------------------------
struct Rng {
  uint32_t s = 0x12345678u;
  inline float next() {   // -1..1
    s ^= s << 13; s ^= s >> 17; s ^= s << 5;
    return (int32_t)s * (1.0f / 2147483648.0f);
  }
};

struct Pink {   // Paul Kellet's economy pink filter
  float b0 = 0, b1 = 0, b2 = 0;
  inline float next(float w) {
    b0 = 0.99765f * b0 + w * 0.0990460f;
    b1 = 0.96300f * b1 + w * 0.2965164f;
    b2 = 0.57000f * b2 + w * 1.0526913f;
    return (b0 + b1 + b2 + w * 0.1848f) * 0.2f;
  }
};

inline float poly_blep(float t, float dt) {
  if (t < dt) { t /= dt; return t + t - t * t - 1.0f; }
  if (t > 1.0f - dt) { t = (t - 1.0f) / dt; return t * t + t + t + 1.0f; }
  return 0.0f;
}

// TPT state variable filter (Zavalishin), used as the 2-pole lowpass and as the resonators' bandpasses.
struct Svf {
  float s1 = 0, s2 = 0;
  inline void reset() { s1 = s2 = 0; }
  // returns lowpass; bp written to *bp
  inline float tick(float x, float g, float k, float *bp) {
    float hp = (x - (g + k) * s1 - s2) / (1.0f + g * (g + k));
    float v1 = g * hp, b = v1 + s1;
    s1 = b + v1;
    float v2 = g * b, l = v2 + s2;
    s2 = l + v2;
    *bp = b;
    return l;
  }
};
inline float svf_g(float hz) { return tanf(PI * clampf(hz, 10.0f, 18000.0f) * INV_SR); }

struct Delay {   // ensemble delay line
  static const int N = 2048;
  float buf[N];
  int w = 0;
  void reset() { memset(buf, 0, sizeof buf); w = 0; }
  inline void push(float x) { buf[w] = x; w = (w + 1) & (N - 1); }
  inline float read(float d) {   // d in samples (>= 1)
    float p = (float)w - d;
    while (p < 0) p += N;
    int i = (int)p;
    float f = p - i;
    float a = buf[i & (N - 1)], b = buf[(i + 1) & (N - 1)];
    return a + (b - a) * f;
  }
};

// ---- voices -------------------------------------------------------------------------------------------------------
enum { ST_OFF, ST_ATTACK, ST_DECAY, ST_SUSTAIN, ST_RELEASE };

struct Voice {
  int note = -1;
  float vel = 1.0f;
  int stage = ST_OFF;
  bool gate = false, held_by_hold = false;
  float env = 0;
  float phase = 0, inc = 0, width = 0.5f;
  float g = 0.1f, k = 1.4f;        // filter coefficients
  float amp = 1.0f;                // velocity x keyboard balance
  Svf f;
  uint32_t age = 0;
};

// ---- the instrument -----------------------------------------------------------------------------------------------
struct Synth {
  float pv[P_COUNT];                // parameter values (native units; options = index)
  int view = 0, held = -1;
  int held_in = -1;                 // an input tapped first, waiting for its output (patching works in either order)
  int pk = 0;                       // the patch step (spec.PK_STEPS): 0 off the page, 1 choose, 2-5 the other end, 6 connected
  int pair_o = -1, pair_j = -1;     // the cable the connected page shows
  int dest[N_OUTS];                 // output -> input it is patched to, -1 = none
  int src[N_INS];                   // input -> output feeding it, -1 = none (derived from dest)
  unsigned rev = 1;                 // display_rev
  int last_jack = -1;               // patch_info: the jack tapped last (outputs, then inputs)
  char info[128];
  unsigned n_tap = 0, n_lo = 0, n_set = 0;   // diagnostics: jack taps that arrived (value >= .5 / below), any set
  int last_set = -1;
  bool hold_active = false;
  bool pop_open[N_POPS] = {};       // pop_<key>: which pop-up list is open (at most one; closed on a pick or a page change)

  // patch bay values, this sample
  float out_v[N_OUTS];
  bool trig_kbd_single = false, trig_kbd_multi = false;

  // MIDI state
  int keys_down = 0;
  bool key_held[128];
  int last_note = 60;
  float pb = 0, mw = 0;             // -1..1, 0..1
  float vc[4] = {0, 0, 0, 0};       // -1..1
  bool trg_pending[2] = {false, false};
  int cc_last[128];
  bool sustain_pedal = false;

  // modulation generators
  float mg1_phase = 0, mg2_phase = 0, sh_phase = 0, clk_phase[2] = {0, 0};
  float sh_value = 0;
  float mg1_noise_hold = 0;
  Rng rng;
  Pink pink;
  // GEG
  int geg_stage = 0;                // 0 idle, 1 delay, 2 attack, 3 sustain, 4 release
  float geg_env = 0, geg_delay_left = 0;
  bool geg_led = false;
  float bpm = 120.0f;
  float tune[12];

  Voice voices[MAX_VOICES];
  uint32_t age_counter = 0;
  int ctrl_count = 0;

  // global audio
  Svf res[3];
  Delay ens;
  float ens_phase[3] = {0, 0.3333f, 0.6667f}, ens_fast = 0;
  plateau::Limiter lim;
  float dc_l = 0, dc_r = 0, dcx_l = 0, dcx_r = 0;

  // smoothing of the output stage gains
  float s_final = 0, s_direct = 0;

  void init() {
    for (int i = 0; i < P_COUNT; i++) pv[i] = P_DEF[i];
    for (int i = 0; i < N_OUTS; i++) { dest[i] = -1; out_v[i] = 0; }
    for (int i = 0; i < N_INS; i++) src[i] = -1;
    memset(key_held, 0, sizeof key_held);
    for (int i = 0; i < 128; i++) cc_last[i] = 0;
    ens.reset();
    lim.Init();
    snprintf(info, sizeof info, "Tap an output, then an input. Tap a patched output to unplug it.");
    apply_tuning();
  }

  // ---- parameters ------------------------------------------------------------------------------------------------
  inline float P(int i) const { return pv[i]; }
  inline int Pi(int i) const { return (int)lroundf(pv[i]); }
  bool on(int i) const { return Pi(i) != 0; }

  void apply_tuning() {
    for (int i = 0; i < 12; i++) tune[i] = pv[P_TUNE_C + i];
  }

  void update_hold() {
    bool sw = on(P_EM_HOLD);
    if (!on(P_PS_HOLD_MODE)) hold_active = sw;
    else if (sw && pv[P_EM_ATTACK] > 7.0f) hold_active = true;        // the PS-3100's hold: attack past ~70% to engage
    else if (!sw && pv[P_EM_ATTACK] < 3.0f) hold_active = false;      // and under ~30% to let go
    if (!hold_active)
      for (int i = 0; i < MAX_VOICES; i++)
        if (voices[i].held_by_hold && !voices[i].gate) { voices[i].held_by_hold = false; release_voice(voices[i]); }
  }

  void recompute_src() {
    for (int i = 0; i < N_INS; i++) src[i] = -1;
    for (int o = 0; o < N_OUTS; o++)
      if (dest[o] >= 0) src[dest[o]] = o;
  }

  void bump() { rev++; }

  // ---- notes ---------------------------------------------------------------------------------------------------------
  int voice_count() const { return VOICE_COUNTS[(int)clampf(pv[P_VOICES], 0, 5)]; }

  void release_voice(Voice &v) {
    if (v.stage != ST_OFF) v.stage = ST_RELEASE;
  }

  void note_on(int note, int vel) {
    int n = voice_count();
    Voice *best = nullptr;
    for (int i = 0; i < n; i++)            // the same key again: retrigger its voice
      if (voices[i].note == note && voices[i].stage != ST_OFF) { best = &voices[i]; break; }
    if (!best)
      for (int i = 0; i < n; i++)
        if (voices[i].stage == ST_OFF) { best = &voices[i]; break; }
    if (!best) {                           // steal: the oldest releasing voice, else the oldest
      uint32_t oldest = 0xffffffffu;
      for (int i = 0; i < n; i++)
        if (voices[i].stage == ST_RELEASE && voices[i].age < oldest) { oldest = voices[i].age; best = &voices[i]; }
      if (!best)
        for (int i = 0; i < n; i++)
          if (voices[i].age < oldest) { oldest = voices[i].age; best = &voices[i]; }
    }
    Voice &v = *best;
    bool fresh = v.stage == ST_OFF;
    v.note = note;
    v.vel = vel / 127.0f;
    v.gate = true;
    v.held_by_hold = false;
    v.stage = ST_ATTACK;
    v.age = ++age_counter;
    if (fresh) { v.env = 0; v.f.reset(); v.phase = (rng.next() + 1.0f) * 0.5f; }   // free-running dividers: any phase
    update_voice(v, 0, 0, 0, 0, true);
    if (!key_held[note]) { key_held[note] = true; keys_down++; }
    if (keys_down == 1) trig_kbd_single = true;
    trig_kbd_multi = true;
    last_note = note;
    if (on(P_SH_SYNC)) sh_phase = 0;        // S/H synchro: the clock starts again with the key
  }

  void note_off(int note) {
    if (key_held[note]) { key_held[note] = false; keys_down--; }
    for (int i = 0; i < MAX_VOICES; i++) {
      Voice &v = voices[i];
      if (v.note != note || !v.gate) continue;
      v.gate = false;
      if (hold_active || sustain_pedal) v.held_by_hold = true;
      else release_voice(v);
    }
  }

  void all_off() {
    for (int i = 0; i < MAX_VOICES; i++) { voices[i].stage = ST_OFF; voices[i].env = 0; voices[i].gate = false; }
    memset(key_held, 0, sizeof key_held);
    keys_down = 0;
  }

  void midi(const uint8_t *m, int len) {
    if (len < 1) return;
    int st = m[0] & 0xF0;
    int d1 = len > 1 ? m[1] & 127 : 0, d2 = len > 2 ? m[2] & 127 : 0;
    if (st == 0x90 && d2 > 0) note_on(d1, d2);
    else if (st == 0x80 || (st == 0x90 && d2 == 0)) note_off(d1);
    else if (st == 0xE0) pb = clampf(((d2 << 7 | d1) - 8192) / 8192.0f, -1, 1);
    else if (st == 0xB0) {
      if (d1 == 1) mw = d2 / 127.0f;
      if (d1 == 64) {
        sustain_pedal = d2 >= 64;
        if (!sustain_pedal) update_hold();
        if (!sustain_pedal && !hold_active)
          for (int i = 0; i < MAX_VOICES; i++)
            if (voices[i].held_by_hold && !voices[i].gate) { voices[i].held_by_hold = false; release_voice(voices[i]); }
      }
      if (d1 == 120 || d1 == 123) all_off();
      for (int i = 0; i < 4; i++)
        if (d1 == Pi(P_VC1_CC + i)) vc[i] = d2 / 63.5f - 1.0f;
      for (int i = 0; i < 2; i++)                 // a trigger fires when the controller falls past the middle
        if (d1 == Pi(P_TRG1_CC + i) && cc_last[d1] > 63 && d2 < 63) trg_pending[i] = true;
      cc_last[d1] = d2;
    }
  }

  // ---- the patch bay -------------------------------------------------------------------------------------------------
  // input value: the output patched in, else the default (dflt)
  inline float in(int j, float dflt) const { return src[j] >= 0 ? out_v[src[j]] : dflt; }
  inline bool patched(int j) const { return src[j] >= 0; }

  float sync_hz(int sync_param, float free_hz) const {
    int s = Pi(sync_param);
    if (s <= 0) return free_hz;
    return bpm / 60.0f / DIV_BEATS[s - 1];
  }

  // all modulation for one sample; triggers are one-sample pulses (1 = fired)
  void modulation() {
    float *o = out_v;
    // performance and constants
    o[O_KEY] = clampf((last_note - 66) / 6.0f, -5, 5);
    o[O_PB] = pb * 5.0f;
    o[O_PBP] = (pb + 1.0f) * 2.5f;
    o[O_MW] = mw * 10.0f - 5.0f;
    o[O_MWP] = mw * 5.0f;
    for (int i = 0; i < 4; i++) o[O_VC1 + i] = vc[i] * 5.0f;
    o[O_RND] = rng.next() * 5.0f;
    o[O_P5V] = 5.0f;
    o[O_M5V] = -5.0f;
    o[O_XYX] = pv[P_XY_X];
    o[O_XYY] = pv[P_XY_Y];
    // keyboard and MIDI triggers
    o[O_SNG] = trig_kbd_single ? 1.0f : 0.0f;
    o[O_MLT] = trig_kbd_multi ? 1.0f : 0.0f;
    trig_kbd_single = trig_kbd_multi = false;
    for (int i = 0; i < 2; i++) { o[O_TRG1 + i] = trg_pending[i] ? 1.0f : 0.0f; trg_pending[i] = false; }
    for (int i = 0; i < 2; i++) {          // tempo clocks
      clk_phase[i] += clk_inc[i];
      o[O_CLK1 + i] = 0;
      if (clk_phase[i] >= 1.0f) { clk_phase[i] -= floorf(clk_phase[i]); o[O_CLK1 + i] = 1.0f; }
    }
    // MG 1: 0.05 Hz .. ~1.6 kHz, 1 V/oct from MG1 FRQ
    float f1 = sync_hz(P_MG1_SYNC, mg1_free);
    if (patched(I_MG1_FRQ)) f1 *= fast_exp2(clampf(in(I_MG1_FRQ, 0), -10, 10));
    mg1_phase += clampf(f1, 0, 5000) * INV_SR;
    o[O_MG1C] = 0;
    if (mg1_phase >= 1.0f) { mg1_phase -= floorf(mg1_phase); o[O_MG1C] = 1.0f; mg1_noise_hold = rng.next(); }
    float ph = mg1_phase, w1;
    switch (Pi(P_MG1_WAVE)) {
      case 0: w1 = ph < 0.5f ? ph * 4.0f - 1.0f : 3.0f - ph * 4.0f; break;
      case 1: w1 = 1.0f - 2.0f * ph; break;
      case 2: w1 = 2.0f * ph - 1.0f; break;
      case 3: w1 = ph < 0.5f ? 1.0f : -1.0f; break;
      case 4: w1 = clampf(pink.next(rng.next()) * 3.0f, -1, 1); break;
      default: w1 = rng.next(); break;
    }
    o[O_MG1] = w1 * 5.0f;
    // MG 2: triangle, 0.05 .. ~200 Hz
    mg2_phase += mg2_hz * INV_SR;
    o[O_MG2C] = 0;
    if (mg2_phase >= 1.0f) { mg2_phase -= floorf(mg2_phase); o[O_MG2C] = 1.0f; }
    o[O_MG2] = (mg2_phase < 0.5f ? mg2_phase * 4.0f - 1.0f : 3.0f - mg2_phase * 4.0f) * 5.0f;
    // S/H: samples its input (MG 1 by default) on its own clock, 0.1 .. ~50 Hz
    sh_phase += sh_hz * INV_SR;
    o[O_SHC] = 0;
    if (sh_phase >= 1.0f) {
      sh_phase -= floorf(sh_phase);
      o[O_SHC] = 1.0f;
      sh_value = in(I_SH_IN, o[O_MG1]);
    }
    o[O_SH] = sh_value;
    // MG signal: MG 1 or S/H, through the MG VCA (MG AMT input; full when unpatched)
    float mgsig = Pi(P_MG_SELECT) == 0 ? o[O_SH] : o[O_MG1];
    float mgamt = patched(I_MG_AMT) ? clampf(in(I_MG_AMT, 5) / 5.0f, 0, 1) : 1.0f;
    o[O_MG] = mgsig * mgamt;
    // GEG: delay / attack / (sustain) / release, started by N keys or by its trigger input
    geg_tick();
    float ge = geg_env * 5.0f;
    o[O_GEP] = ge;
    o[O_GEG] = Pi(P_GEG_POLARITY) == 0 ? ge : -ge;
    // voltage processors: input -5..+5 V mapped between limiter B (bottom) and A (top)
    float vin1 = clampf(in(I_VP1_IN, 0), -5, 5);
    o[O_VP1] = pv[P_VP1_B] + (vin1 + 5.0f) * 0.1f * (pv[P_VP1_A] - pv[P_VP1_B]);
    float vin2 = clampf(Pi(P_VP2_SRC) == 1 ? o[O_VP1] : in(I_VP2_IN, 0), -5, 5);
    o[O_VP2] = pv[P_VP2_B] + (vin2 + 5.0f) * 0.1f * (pv[P_VP2_A] - pv[P_VP2_B]);
    // add amp and junctions
    float add = in(I_ADD1, 0) + in(I_ADD2, 0) + in(I_ADD3, 0) + in(I_ADD4, 0);
    o[O_ADD] = clampf(add * pv[P_ADD_LEVEL] * 0.1f, -10, 10);
    o[O_J1A] = o[O_J1B] = in(I_J1_IN, 0);
    o[O_J2A] = o[O_J2B] = in(I_J2_IN, 0);
    // a release trigger patched into EM REL
    if (patched(I_EM_REL) && in(I_EM_REL, 0) > 0.5f)
      for (int i = 0; i < MAX_VOICES; i++) release_voice(voices[i]);
  }

  void geg_tick() {
    int trig_mode = Pi(P_GEG_TRIGGER);     // 0 off, 1..5 keys
    bool fire = false, hold = false;
    if (patched(I_GEG_TRG)) {
      fire = in(I_GEG_TRG, 0) > 0.5f;      // a trigger has no length: attack, then release
    } else if (trig_mode > 0) {
      hold = keys_down >= trig_mode;
      static_assert(true, "");
      fire = hold && geg_stage == 0;
      if (hold && geg_stage == 4) fire = true;   // keys again while releasing
    }
    bool auto_mode = on(P_GEG_AUTO) || patched(I_GEG_TRG);
    if (fire) { geg_stage = 1; geg_delay_left = knob_time(pv[P_GEG_DELAY]) - 0.001f; }
    switch (geg_stage) {
      case 1:
        geg_delay_left -= INV_SR;
        if (geg_delay_left <= 0) geg_stage = 2;
        break;
      case 2:
        geg_env += geg_atk;
        if (geg_env >= 1.0f) { geg_env = 1.0f; geg_stage = auto_mode ? 4 : 3; }
        break;
      case 3:
        if (!hold) geg_stage = 4;
        break;
      case 4:
        geg_env -= geg_env * geg_rel + 1e-6f;
        if (geg_env <= 0) { geg_env = 0; geg_stage = 0; }
        break;
    }
    if (!auto_mode && geg_stage == 2 && !hold && !patched(I_GEG_TRG)) geg_stage = 4;
    bool led = geg_env > 0.02f;
    if (led != geg_led) { geg_led = led; bump(); }
  }

  // ---- per voice -----------------------------------------------------------------------------------------------------
  // fm_semi: pitch modulation in semitones, cut_oct: cutoff modulation in octaves, pwm: -1..1
  void update_voice(Voice &v, float fm_semi, float cut_oct, float pwm, float atk_cv, bool first = false) {
    static const float OCT[4] = {-12, 0, 12, 24};
    int pc = v.note % 12;
    float semi = v.note - 69 + OCT[Pi(P_SG_OCTAVE) & 3] + pv[P_SG_COARSE] + (pv[P_SG_FINE] + tune[pc] +
                 pv[P_MASTER_TUNE]) * 0.01f + pb * pv[P_PB_RANGE] + fm_semi;
    float hz = 440.0f * fast_exp2(semi / 12.0f);
    v.inc = clampf(hz * INV_SR, 0, 0.45f);
    v.width = clampf(0.5f + pwm * 0.45f, 0.05f, 0.95f);
    // cutoff: knob (20 Hz .. 18 kHz), keyboard tracking (balance), envelope (expand), modulation
    float oct = pv[P_LP_CUTOFF] * 0.98f + pv[P_LP_BALANCE] * 0.2f * (v.note - 60) / 12.0f +
                pv[P_LP_EXPAND] * 0.6f * v.env + cut_oct;
    v.g = svf_g(20.0f * fast_exp2(clampf(oct, 0, 10)));
    v.k = 2.0f - 1.8f * pv[P_LP_PEAK] * 0.1f;   // peak never reaches self-oscillation, as on the PS-3100
    float vel_amt = pv[P_VELOCITY] * 0.1f;
    float bal = fast_exp2(pv[P_KBD_BALANCE] * 0.2f * (v.note - 60) / 24.0f);
    v.amp = (1.0f - vel_amt + vel_amt * v.vel) * clampf(bal, 0.1f, 4.0f);
    (void)first;
    (void)atk_cv;
  }

  inline float osc(Voice &v) {
    float t = v.phase, dt = v.inc, s;
    switch (k_wave) {
      case 0: s = t < 0.5f ? 4.0f * t - 1.0f : 3.0f - 4.0f * t; break;          // triangle
      case 1: s = 2.0f * t - 1.0f - poly_blep(t, dt); break;                    // sawtooth
      default: {                                                                // square / rect / pulse / PWM
        static const float W[6] = {0.5f, 0.5f, 0.5f, 0.25f, 0.1f, 0.5f};
        float pw = k_wave == 5 ? v.width : W[k_wave];
        s = t < pw ? 1.0f : -1.0f;
        s += poly_blep(t, dt);
        float t2 = t - pw + (t < pw ? 1.0f : 0.0f);
        s -= poly_blep(t2, dt);
        s -= 2.0f * pw - 1.0f;                                                  // no DC from narrow pulses
        break;
      }
    }
    v.phase += dt;
    if (v.phase >= 1.0f) v.phase -= 1.0f;
    return s;
  }

  // envelope coefficients, worked out once per block (see begin_block)
  float k_atk = 0, k_dec = 0, k_rel = 0, k_sus = 0;
  int k_wave = 1;

  void begin_block() {
    k_atk = INV_SR / knob_time(pv[P_EM_ATTACK]);
    k_dec = rate_for(knob_time(pv[P_EM_DECAY]) * 0.3f);
    float t;
    if (on(P_REL_OVERRIDE)) t = knob_time(pv[P_REL_TIME]);
    else {
      int r = Pi(P_EM_RELEASE);
      t = r == 0 ? 0.006f : r == 1 ? 0.12f : knob_time(pv[P_EM_DECAY]);   // damp / half damp / release
    }
    k_rel = rate_for(t * 0.3f);
    k_sus = pv[P_EM_SUSTAIN] * 0.1f;
    k_wave = Pi(P_SG_WAVE);
    mg1_free = 0.05f * fast_exp2(pv[P_MG1_FREQ] * 1.5f);
    mg2_hz = sync_hz(P_MG2_SYNC, 0.05f * fast_exp2(pv[P_MG2_FREQ] * 1.2f));
    sh_hz = sync_hz(P_SH_HOST, 0.1f * fast_exp2(pv[P_SH_CLOCK] * 0.9f));
    geg_atk = INV_SR / knob_time(pv[P_GEG_ATTACK]);
    geg_rel = rate_for(knob_time(pv[P_GEG_RELEASE]) * 0.3f);
    for (int i = 0; i < 2; i++) clk_inc[i] = bpm / 60.0f / DIV_BEATS[Pi(P_CLK1_RATE + i)] * INV_SR;
  }
  float mg1_free = 1, mg2_hz = 1, sh_hz = 1, geg_atk = 0, geg_rel = 0, clk_inc[2] = {0, 0};

  inline void env_tick(Voice &v, float atk_mul) {
    switch (v.stage) {
      case ST_ATTACK:
        v.env += k_atk * atk_mul;
        if (v.env >= 1.0f) { v.env = 1.0f; v.stage = ST_DECAY; }
        break;
      case ST_DECAY:
        v.env += (k_sus - v.env) * k_dec;
        if (fabsf(v.env - k_sus) < 1e-4f) v.stage = ST_SUSTAIN;
        break;
      case ST_SUSTAIN:
        v.env = k_sus;
        break;
      case ST_RELEASE:
        v.env -= v.env * k_rel + 2e-7f;
        if (v.env <= 0.0f) { v.env = 0; v.stage = ST_OFF; v.note = -1; }
        break;
      default: break;
    }
  }

  // ---- render --------------------------------------------------------------------------------------------------------
  void render(int16_t *out, int frames) {
    ScopedDenormalDisable dg;
    begin_block();
    if (!patched(I_EM_ATK)) atk_mul_cur = 1.0f;
    float bl[128], br[128];
    int nv = voice_count();
    for (int i = nv; i < MAX_VOICES; i++) if (voices[i].stage != ST_OFF) { voices[i].stage = ST_OFF; voices[i].env = 0; }
    float tgt_final = pv[P_FINAL_VOL] * 0.1f, tgt_direct = pv[P_DIRECT_VOL] * 0.1f;
    tgt_final = tgt_final * tgt_final * 1.4f;
    tgt_direct = tgt_direct * tgt_direct * 1.4f;
    float voice_norm = 0.3f;
    float fpan = pv[P_FINAL_PAN] * 0.1f + 0.5f, dpan = pv[P_DIRECT_PAN] * 0.1f + 0.5f;
    float fl = cosf(fpan * PI * 0.5f) * 1.41421f, fr = sinf(fpan * PI * 0.5f) * 1.41421f;
    float dl = cosf(dpan * PI * 0.5f) * 1.41421f, dr = sinf(dpan * PI * 0.5f) * 1.41421f;
    for (int n = 0; n < frames; n++) {
      modulation();
      const float *o = out_v;
      // modulation that the voices share
      bool control = (ctrl_count++ % CTRL_EVERY) == 0;
      float fm_semi = 0, cut_oct = 0, pwm = 0, atk_scale = 1.0f;
      if (control) {
        if (on(P_SG_FM_ON)) {
          fm_semi = o[O_MG] * pv[P_SG_FM_MG1] * 0.024f * 10.0f / 10.0f + in(I_SG_FRQ, o[O_GEG]) * pv[P_SG_FM_GEG] * 0.24f;
          if (on(P_SG_FM_REV)) fm_semi = -fm_semi;
        }
        if (on(P_LP_FM_ON))
          cut_oct = o[O_MG] * pv[P_LP_FM_MG1] * 0.08f + in(I_LP_FRQ, o[O_GEG]) * pv[P_LP_FM_GEG] * 0.08f;
        pwm = clampf(in(I_SG_PWM, o[O_MG2]) * 0.2f * pv[P_SG_PWM_INT] * 0.1f, -1, 1);
      }
      if (control && patched(I_EM_ATK)) atk_mul_cur = fast_exp2(clampf(in(I_EM_ATK, 0), -5, 5));
      atk_scale = atk_mul_cur;
      float sum = 0;
      for (int i = 0; i < nv; i++) {
        Voice &v = voices[i];
        if (v.stage == ST_OFF) continue;
        if (control) update_voice(v, fm_semi, cut_oct, pwm, 0);
        env_tick(v, atk_scale);
        float s = osc(v), bp;
        // a touch of drive before the filter, like an OTA input
        s = s / (1.0f + 0.25f * fabsf(s));
        float l = v.f.tick(s, v.g, v.k, &bp);
        sum += l * v.env * v.amp;
      }
      sum *= voice_norm;
      float direct = sum;
      // resonators: three bandpass peaks, 100 Hz .. 10 kHz, moved by MG 2 and the RES FRQ input
      float ri = pv[P_RES_INT] * 0.1f, x = sum;
      if (ri > 0.001f) {
        float roct = 0;
        if (on(P_RES_MG2)) roct += o[O_MG2] * 0.1f;
        roct += in(I_RES_FRQ, 0) * pv[P_RES_EXT] * 0.04f;
        float acc = 0, bp;
        for (int r = 0; r < 3; r++) {
          float hz = 100.0f * fast_exp2(clampf(pv[P_RES_F1 + r] * 0.6644f + roct, 0, 7.5f));
          if (control || n == 0) res_g[r] = svf_g(hz);
          res[r].tick(x, res_g[r], 0.18f, &bp);
          acc += bp;
        }
        x = x * (1.0f - ri) + acc * 0.6f * ri;
      }
      // amplitude modulator, by MG 1: cross modulation up to the middle of the knob, ring modulation past it
      if (on(P_AM_MG1)) {
        float m = o[O_MG1] * 0.2f, a = pv[P_AMP_MOD] * 0.1f;
        if (a <= 0.5f) x *= 1.0f - a * (1.0f - m);
        else { float r = (a - 0.5f) * 2.0f; x *= (1.0f - r) * (0.5f + 0.5f * m) + r * m; }
      }
      // ensemble: three modulated delay taps
      float L = x, R = x;
      if (on(P_ENSEMBLE)) {
        ens.push(x);
        ens_fast += 6.3f * INV_SR;
        if (ens_fast >= 1.0f) ens_fast -= 1.0f;
        float fast = sinf(2.0f * PI * ens_fast) * 0.15f;
        float t[3];
        for (int k = 0; k < 3; k++) {
          ens_phase[k] += 0.63f * INV_SR;
          if (ens_phase[k] >= 1.0f) ens_phase[k] -= 1.0f;
          float d = (7.0f + 2.2f * sinf(2.0f * PI * ens_phase[k]) + fast) * 44.1f;
          t[k] = ens.read(d);
        }
        L = x * 0.6f + t[0] * 0.7f + t[1] * 0.35f;
        R = x * 0.6f + t[2] * 0.7f + t[1] * 0.35f;
      }
      // VCA 1 (GEG by default) and VCA 2 (VP 1 by default)
      if (on(P_VCA1_GEG)) { float g = clampf(in(I_VCA1, o[O_GEG]) * 0.2f, 0, 1); L *= g; R *= g; }
      if (on(P_VCA2_VP1)) { float g = clampf(in(I_VCA2, o[O_VP1]) * 0.2f, 0, 1); L *= g; R *= g; }
      s_final += (tgt_final - s_final) * 0.002f;
      s_direct += (tgt_direct - s_direct) * 0.002f;
      float outl = L * s_final * fl + direct * s_direct * dl;
      float outr = R * s_final * fr + direct * s_direct * dr;
      // DC blocker
      float yl = outl - dcx_l + 0.9995f * dc_l, yr = outr - dcx_r + 0.9995f * dc_r;
      dcx_l = outl; dcx_r = outr; dc_l = yl; dc_r = yr;
      bl[n] = yl;
      br[n] = yr;
    }
    lim.Process(bl, br, frames, 0.0f, -0.3f, 80.0f, SR);
    for (int n = 0; n < frames; n++) {
      float a = bl[n] * 32767.0f, b = br[n] * 32767.0f;
      out[n * 2] = (int16_t)(a > 32767.0f ? 32767 : a < -32768.0f ? -32768 : lrintf(a));
      out[n * 2 + 1] = (int16_t)(b > 32767.0f ? 32767 : b < -32768.0f ? -32768 : lrintf(b));
    }
  }
  float res_g[3] = {0.1f, 0.1f, 0.1f};
  float atk_mul_cur = 1.0f;

  // ---- UI: views, jacks, Q-Links -----------------------------------------------------------------------------------------
  void set_view(int v) {
    if (v < 0 || v >= N_VIEWS || v == view) return;
    view = v;
    close_pops();   // a list left open would stay on screen over the next page and take its touches
    held = held_in = -1;
    pk = v == V_PATCH ? 1 : 0;
    if (pk) snprintf(info, sizeof info, "Tap a jack. Then tap the other end of the cable.");
    bump();
  }

  bool close_pops() {
    bool any = false;
    for (int i = 0; i < N_POPS; i++) if (pop_open[i]) { pop_open[i] = false; any = true; }
    return any;
  }

  void set_pop(int i, bool open) {
    if (open) close_pops();   // one list at a time
    pop_open[i] = open;
    bump();
  }

  void describe_jack(int jack) {
    last_jack = jack;
    if (jack < N_OUTS) {
      int d = dest[jack];
      if (held == jack) snprintf(info, sizeof info, "%s: now tap an input  (%s)", OUT_LABEL[jack], OUT_INFO[jack]);
      else if (d >= 0) snprintf(info, sizeof info, "%s -> %s   (tap %s to unplug)", OUT_LABEL[jack], IN_LABEL[d], OUT_LABEL[jack]);
      else snprintf(info, sizeof info, "%s: %s", OUT_LABEL[jack], OUT_INFO[jack]);
    } else {
      int j = jack - N_OUTS;
      if (held_in == j) snprintf(info, sizeof info, "%s: now tap an output  (%s)", IN_LABEL[j], IN_INFO[j]);
      else if (src[j] >= 0) snprintf(info, sizeof info, "%s <- %s   (%s)", IN_LABEL[j], OUT_LABEL[src[j]], IN_INFO[j]);
      else snprintf(info, sizeof info, "%s: %s", IN_LABEL[j], IN_INFO[j]);
    }
  }

  // Patching in either order: tap an output then an input, or an input then an output. A cable always joins one output
  // to one input of the same kind (voltage or trigger); two outputs or two inputs in a row just move the selection.
  bool connect(int o, int j) {
    if (OUT_TRIG[o] != IN_TRIG[j]) {
      snprintf(info, sizeof info, "%s is a %s output; %s takes %s", OUT_LABEL[o], OUT_TRIG[o] ? "trigger" : "voltage",
               IN_LABEL[j], IN_TRIG[j] ? "triggers" : "voltages");
      return false;
    }
    for (int k = 0; k < N_OUTS; k++) if (dest[k] == j) dest[k] = -1;   // one cable per input
    dest[o] = j;                                                       // one cable per output
    recompute_src();
    return true;
  }

  // Patching by pages (0.1.5): every jack is a big tile. Tap one; the page then asks for the other end, with the wrong
  // kinds dimmed (a voltage output only joins a voltage input, a trigger only a trigger) and ignored; connecting opens the
  // page that shows the cable. A tapped jack that is already patched opens that cable's page instead (UNPLUG is there).
  void show_pair(int o, int j) {
    pair_o = o; pair_j = j; pk = 6; held = held_in = -1;
    snprintf(info, sizeof info, "%s  ->  %s", OUT_LABEL[o], IN_LABEL[j]);
    bump();
  }

  void cancel_pick() {
    held = held_in = -1; pk = view == V_PATCH ? 1 : 0;
    snprintf(info, sizeof info, "Tap a jack. Then tap the other end of the cable.");
    bump();
  }

  void unplug_pair() {
    if (pk == 6 && pair_o >= 0 && dest[pair_o] == pair_j) {
      dest[pair_o] = -1; recompute_src();
      snprintf(info, sizeof info, "%s unplugged", OUT_LABEL[pair_o]);
      pair_o = pair_j = -1; held = held_in = -1; pk = 1; bump();
    } else cancel_pick();
  }

  void done_pick() { cancel_pick(); }

  void pick(int jack) {
    if (view != V_PATCH || pk < 1 || pk > 5) return;
    bool is_out = jack < N_OUTS;
    int o = is_out ? jack : -1, j = is_out ? -1 : jack - N_OUTS;
    if (pk == 1) {
      if (is_out) {
        if (dest[o] >= 0) { show_pair(o, dest[o]); return; }
        held = o; pk = OUT_TRIG[o] ? 3 : 2;
        snprintf(info, sizeof info, "%s: now tap an input (%s)", OUT_LABEL[o], OUT_TRIG[o] ? "triggers" : "voltages");
      } else {
        if (src[j] >= 0) { show_pair(src[j], j); return; }
        held_in = j; pk = IN_TRIG[j] ? 5 : 4;
        snprintf(info, sizeof info, "%s: now tap an output (%s)", IN_LABEL[j], IN_TRIG[j] ? "triggers" : "voltages");
      }
    } else if (pk == 2 || pk == 3) {                // an output waits for an input of its kind
      if (is_out) { if (o == held) cancel_pick(); return; }
      if (IN_TRIG[j] != OUT_TRIG[held]) return;
      int oo = held;
      connect(oo, j);
      show_pair(oo, j);
      return;
    } else {                                        // an input waits for an output of its kind
      if (!is_out) { if (j == held_in) cancel_pick(); return; }
      if (OUT_TRIG[o] != IN_TRIG[held_in]) return;
      int jj = held_in;
      connect(o, jj);
      show_pair(o, jj);
      return;
    }
    last_jack = jack;
    bump();
  }

  int cable_value(int o) const {
    if (dest[o] < 0) return 0;
    int typed = IN_TYPED[dest[o]], n = OUT_TRIG[o] ? N_TRIG_INS : N_CV_INS;
    if (view == V_PATCH) return 1 + typed;
    if (view == V_OVERVIEW) return 1 + n + typed;
    return 0;
  }

  // the cable / ring picture switches (0.1.4): each at most JACK_GROUP + 1 positions (see tools/spec.py)
  int vis_value(int k) const {
    if (VIS_KIND[k] == 2) {                        // ring: the output waiting for its input, on the patch page
      if (view != V_PATCH || held < 0 || held / JACK_GROUP != VIS_GROUP[k]) return 0;
      return 1 + held % JACK_GROUP;
    }
    if (VIS_KIND[k] == 3) {                        // ring: the input waiting for its output
      if (view != V_PATCH || held_in < 0 || held_in / JACK_GROUP != VIS_GROUP[k]) return 0;
      return 1 + held_in % JACK_GROUP;
    }
    if (view != (VIS_KIND[k] == 0 ? V_PATCH : V_OVERVIEW)) return 0;
    int o = VIS_OUT[k], d = dest[o];
    if (d < 0) return 0;
    int t = IN_TYPED[d];
    return t / JACK_GROUP == VIS_GROUP[k] ? 1 + t % JACK_GROUP : 0;
  }

  int ql_target(int i) const { return VIEW_QLINKS[view][i]; }

  // ---- value text ------------------------------------------------------------------------------------------------------
  void display(int p, char *buf, int n) const {
    if (P_NOPTS[p]) { snprintf(buf, n, "%s", P_OPT[p][(int)clampf(pv[p], 0, P_NOPTS[p] - 1)]); return; }
    float v = pv[p];
    const char *u = P_UNIT[p];
    if (p == P_FINAL_PAN || p == P_DIRECT_PAN) {
      if (fabsf(v) < 0.05f) snprintf(buf, n, "C");
      else snprintf(buf, n, "%s %.1f", v < 0 ? "L" : "R", fabsf(v));
      return;
    }
    if (P_INT[p]) snprintf(buf, n, "%s%d%s%s", (p >= P_TUNE_C && p <= P_TUNE_B) || p == P_SG_FINE || p == P_SG_COARSE ||
                           p == P_MASTER_TUNE ? (v > 0.5f ? "+" : "") : "", (int)lroundf(v), *u ? " " : "", u);
    else snprintf(buf, n, "%.1f%s%s", v, *u ? " " : "", u);
  }

  // ---- state ---------------------------------------------------------------------------------------------------------------
  int save(char *buf, int n) const {
    int len = snprintf(buf, n, "ps3100xxl 1;");
    for (int i = 0; i < N_CONTROLS && len < n; i++) len += snprintf(buf + len, n - len, "%s=%g;", P_KEY[i], pv[i]);
    if (len < n) len += snprintf(buf + len, n - len, "view=%d;", view);
    for (int o = 0; o < N_OUTS && len < n; o++)
      if (dest[o] >= 0) len += snprintf(buf + len, n - len, "cable=%s>%s;", OUT_KEY[o], IN_KEY[dest[o]]);
    return len < n ? len : -1;
  }
};

int find_key(const char *k) {
  // open-addressing hash of the parameter keys, built once
  static int table[1024];
  static bool built = false;
  auto h = [](const char *s) { uint32_t x = 2166136261u; while (*s) x = (x ^ (unsigned char)*s++) * 16777619u; return x; };
  if (!built) {
    for (int i = 0; i < 1024; i++) table[i] = -1;
    for (int i = 0; i < P_COUNT; i++) {
      uint32_t s = h(P_KEY[i]) & 1023;
      while (table[s] >= 0) s = (s + 1) & 1023;
      table[s] = i;
    }
    built = true;
  }
  uint32_t s = h(k) & 1023;
  while (table[s] >= 0) {
    if (!strcmp(P_KEY[table[s]], k)) return table[s];
    s = (s + 1) & 1023;
  }
  return -1;
}

int find_in(const char *a, const char *const *keys, int n) {
  for (int i = 0; i < n; i++) if (!strcmp(a, keys[i])) return i;
  return -1;
}

void set_control(Synth *s, int p, float v);

void load_state(Synth *s, const char *st) {
  if (strncmp(st, "ps3100xxl", 9)) return;
  for (int o = 0; o < N_OUTS; o++) s->dest[o] = -1;
  const char *q = strchr(st, ';');
  while (q && *++q) {
    const char *e = strchr(q, ';');
    if (!e) break;
    char item[96];
    int len = (int)(e - q) < 95 ? (int)(e - q) : 95;
    memcpy(item, q, len);
    item[len] = 0;
    char *eq = strchr(item, '=');
    if (eq) {
      *eq = 0;
      const char *val = eq + 1;
      if (!strcmp(item, "view")) s->view = (int)clampf((float)atoi(val), 0, N_VIEWS - 1);
      else if (!strcmp(item, "cable")) {
        char a[48];
        snprintf(a, sizeof a, "%s", val);
        char *gt = strchr(a, '>');
        if (gt) {
          *gt = 0;
          int o = find_in(a, OUT_KEY, N_OUTS), j = find_in(gt + 1, IN_KEY, N_INS);
          if (o >= 0 && j >= 0 && OUT_TRIG[o] == IN_TRIG[j]) {
            for (int k = 0; k < N_OUTS; k++) if (s->dest[k] == j) s->dest[k] = -1;
            s->dest[o] = j;
          }
        }
      } else {
        int p = find_key(item);
        if (p >= 0 && p < N_CONTROLS && p != P_TEMPERAMENT) set_control(s, p, (float)atof(val));
        else if (p == P_TEMPERAMENT) s->pv[p] = clampf((float)atof(val), 0, P_MAX[p]);
      }
    }
    q = e;
  }
  s->held = -1;
  s->held_in = -1;
  s->recompute_src();
  s->apply_tuning();
  s->update_hold();
  s->bump();
}

void set_control(Synth *s, int p, float v) {
  v = clampf(v, P_MIN[p], P_MAX[p]);
  if (P_NOPTS[p] || P_INT[p]) v = roundf(v);
  bool moved = s->pv[p] != v;
  s->pv[p] = v;
  if (p >= P_TUNE_C && p <= P_TUNE_B) s->apply_tuning();
  if (p == P_TEMPERAMENT) {                 // a template: write its offsets into the twelve tune knobs
    for (int i = 0; i < 12; i++) s->pv[P_TUNE_C + i] = roundf(TEMPERAMENT_CENTS[(int)v][i]);
    s->apply_tuning();
    s->bump();
  }
  if (p == P_EM_HOLD || p == P_PS_HOLD_MODE || p == P_EM_ATTACK) s->update_hold();
  if (p == P_MANUAL_TRG1 && v > 0.5f) { s->trg_pending[0] = true; s->pv[p] = 0; }
  for (int i = 0; i < N_POPS; i++)          // a pick from a pop-up list closes it
    if (POP_ENUM[i] == p && moved && s->pop_open[i]) { s->pop_open[i] = false; s->bump(); }   // not on a re-send
}

// ---- mpc_engine glue ------------------------------------------------------------------------------------------------
void *create(const char *) {
  void *mem = calloc(1, sizeof(Synth));
  if (!mem) return nullptr;
  Synth *s = new (mem) Synth();
  s->init();
  return s;
}

void destroy(void *inst) {
  Synth *s = (Synth *)inst;
  s->~Synth();
  free(s);
}

void midi(void *inst, const uint8_t *m, int len) { ((Synth *)inst)->midi(m, len); }

void set_param(void *inst, const char *key, const char *val) {
  Synth *s = (Synth *)inst;
  float v = (float)atof(val);
  if (!strcmp(key, "state")) { load_state(s, val); return; }
  if (!strcmp(key, "lfo_bpm")) { if (v > 1) s->bpm = v; return; }
  if (!strcmp(key, "transport")) { if (v > 0.5f) s->clk_phase[0] = s->clk_phase[1] = 0; return; }
  int p = find_key(key);
  if (p < 0) return;
  s->n_set++; s->last_set = p;
  if (p >= P_TAP_GEG && p < P_TAP_GEG + N_OUTS + N_INS) { if (v >= 0.5f) s->n_tap++; else s->n_lo++; }
  if (p < N_CONTROLS) {
    set_control(s, p, v);
    s->bump();                              // the Q-Link knob mirroring it moves too
    return;
  }
  if (p == P_VIEW) { s->set_view((int)lroundf(v)); return; }
  if (p == P_IN_SEC) return;                // follows the view
  if (p == P_PK || p == P_PK_T || p == P_PK_C) return;   // follow the patch step
  if (p > P_IN_SEC && p <= P_IN_SEC + N_POPS) { s->set_pop(p - P_IN_SEC - 1, v > 0.5f); return; }
  if (v < 0.5f && p != P_VIEW) {
    if (p >= P_QL1 && p <= P_QL16) {} else return;   // triggers fire on 1 only
  }
  if (p == P_NAV_ZOOM) { s->set_view(V_OVERVIEW); return; }
  if (p == P_NAV_PREV || p == P_NAV_NEXT) {
    int v2 = s->view <= 0 ? 1 : s->view + (p == P_NAV_NEXT ? 1 : -1);
    if (v2 < 1) v2 = N_VIEWS - 1;
    if (v2 >= N_VIEWS) v2 = 1;
    s->set_view(v2);
    return;
  }
  if (p >= P_GO_SG && p < P_GO_SG + (N_VIEWS - 1)) { s->set_view(1 + p - P_GO_SG); return; }
  if (p >= P_TAP_GEG && p < P_TAP_GEG + N_OUTS + N_INS) {
    int jack = p - P_TAP_GEG;
    s->pick(jack);
    return;
  }
  if (p == P_PK_CANCEL) { s->cancel_pick(); return; }
  if (p == P_PK_UNPLUG) { s->unplug_pair(); return; }
  if (p == P_PK_DONE) { s->done_pick(); return; }
  if (p >= P_QL1 && p <= P_QL16) {
    int t = s->ql_target(p - P_QL1);
    if (t < 0) return;
    float x = clampf(v, 0, 1);
    set_control(s, t, P_MIN[t] + x * (P_MAX[t] - P_MIN[t]));
    s->bump();
    return;
  }
  // cab_*, held, geg_led, patch_info: display only, set by the engine
}

int get_param(void *inst, const char *key, char *buf, int n) {
  Synth *s = (Synth *)inst;
  if (!strcmp(key, "display_rev")) return snprintf(buf, n, "%u", s->rev);
  if (!strcmp(key, "state")) return s->save(buf, n);
  size_t kl = strlen(key);
  char base[64];
  int suffix = 0;   // 1 = _display, 2 = _name
  if (kl > 8 && !strcmp(key + kl - 8, "_display")) { suffix = 1; kl -= 8; }
  else if (kl > 5 && !strcmp(key + kl - 5, "_name")) { suffix = 2; kl -= 5; }
  if (kl >= sizeof base) return 0;
  memcpy(base, key, kl);
  base[kl] = 0;
  int p = find_key(base);
  if (p < 0) return 0;
  if (p >= P_QL1 && p <= P_QL16) {
    int t = s->ql_target(p - P_QL1);
    if (suffix == 2) return snprintf(buf, n, "%s", t >= 0 ? P_NAME[t] : "-");
    if (suffix == 1) { if (t < 0) return snprintf(buf, n, " "); s->display(t, buf, n); return (int)strlen(buf); }
    if (t < 0) return snprintf(buf, n, "0");
    float span = P_MAX[t] - P_MIN[t];
    return snprintf(buf, n, "%g", span > 0 ? (s->pv[t] - P_MIN[t]) / span : 0.0f);
  }
  if (suffix == 2) return 0;
  if (suffix == 1) {
    if (p >= N_CONTROLS) return 0;
    s->display(p, buf, n);
    return (int)strlen(buf);
  }
  if (p < N_CONTROLS) {
    if (P_NOPTS[p]) return snprintf(buf, n, "%d", (int)s->pv[p]);
    return snprintf(buf, n, "%g", s->pv[p]);
  }
  if (p == P_VIEW) return snprintf(buf, n, "%d", s->view);
  if (p == P_IN_SEC) return snprintf(buf, n, "%d", s->view > 0 ? 1 : 0);
  if (p == P_PK) return snprintf(buf, n, "%d", s->view == V_PATCH ? s->pk : 0);
  if (p == P_PK_T) return snprintf(buf, n, "%d", s->view == V_PATCH && s->pk >= 1 && s->pk <= 5 ? 1 : 0);
  if (p == P_PK_C) return snprintf(buf, n, "%d", s->view == V_PATCH && s->pk >= 2 && s->pk <= 5 ? 1 : 0);
  if (p >= P_VIS_FIRST && p < P_VIS_FIRST + N_VIS) return snprintf(buf, n, "%d", s->vis_value(p - P_VIS_FIRST));
  if (p > P_IN_SEC && p <= P_IN_SEC + N_POPS) return snprintf(buf, n, "%d", s->pop_open[p - P_IN_SEC - 1] ? 1 : 0);
  if (p >= P_CAB_GEG && p < P_CAB_GEG + N_OUTS) return snprintf(buf, n, "%d", s->cable_value(p - P_CAB_GEG));
  if (p == P_HELD) return snprintf(buf, n, "%d", s->view == V_PATCH && s->held >= 0 ? s->held + 1 : 0);
  if (p == P_GEG_LED) return snprintf(buf, n, "%d", s->geg_led && s->view == V_GEG ? 1 : 0);
  if (p == P_PATCH_INFO) return snprintf(buf, n, "[taps %u low %u sets %u last %d] %s", s->n_tap, s->n_lo, s->n_set, s->last_set, s->info);
  return snprintf(buf, n, "0");   // triggers and navigation read back as 0
}

void render(void *inst, int16_t *out, int frames) { ((Synth *)inst)->render(out, frames); }

const mpc_engine_t API = {create, destroy, midi, set_param, get_param, render, nullptr};

}  // namespace

extern "C" const mpc_engine_t *mpc_engine(void) { return &API; }
