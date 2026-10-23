/* PS3100XXL UI test through the wrapper (0.1.3): the header buttons, the pop-up lists' engine-owned open flags, the data
 * wheel on a pop-up field's value and a patch cable, as MPC drives them (setParameter, processReplacing, automate).
 * Built and run by test/run_tests.sh against the plugin's generated params.h; scaffolding from mpc-vst-plugins' host_test.c. */

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <pthread.h>
#include "params.h"
typedef struct AEffect AEffect;
typedef intptr_t (*cb)(AEffect*,int32_t,int32_t,intptr_t,void*,float);
struct AEffect { int32_t magic; intptr_t (*d)(AEffect*,int32_t,int32_t,intptr_t,void*,float);
 void*p; void (*setP)(AEffect*,int32_t,float); float (*getP)(AEffect*,int32_t);
 int32_t np,npar,ni,no,flags; intptr_t r1,r2; int32_t a,b,c; float io; void*obj,*user; int32_t uid,ver;
 void (*pr)(AEffect*,float**,float**,int32_t); void*pdr; char f[56]; };
typedef struct { int32_t type,byteSize,deltaFrames,flags,noteLength,noteOffset; unsigned char m[4]; char x[4]; } ME;
typedef struct { int32_t n; intptr_t r; void* ev[2]; } EV;
extern AEffect* VSTPluginMain(cb);

static int automated[NPARAMS > 0 ? NPARAMS : 1], fails, updates;   /* updates: audioMasterUpdateDisplay calls */
static double ti[16];                    /* VstTimeInfo: [3] ppqPos, [4] tempo, flags = ((int32_t *)&ti[8])[5] */
static int32_t ti_flags = 1 << 10;       /* tempo valid; transport_tests() adds playing (1 << 1) and ppq valid (1 << 9) */
static intptr_t host(AEffect*e,int32_t op,int32_t i,intptr_t v,void*p,float o){
    if (op == 0 && i >= 0 && i < NPARAMS) { automated[i]++; }
    if (op == 42) updates++;
    if (op == 7) { ti[4] = 120.0; ((int32_t*)&ti[8])[5] = ti_flags; return (intptr_t)ti; }
    return 0;
}


#define CK(c,...) do{ printf("%s ",(c)?"ok  ":"FAIL"); printf(__VA_ARGS__); printf("\n"); if(!(c)) fails++; }while(0)
static void run(AEffect *a, int blocks){ float L[128],R[128],*o[2]={L,R}; for(int k=0;k<blocks;k++) a->pr(a,0,o,128); }
static int fp(const char*k){ for(int i=0;i<NPARAMS;i++) if(!strcmp(PARAMS[i].key,k)) return i; printf("no %s\n",k); exit(1); }
static float g(AEffect*a,const char*k){ return a->getP(a,fp(k)); }
int main(){ AEffect*a=VSTPluginMain(host); a->d(a,12,0,1,0,0); run(a,50);
  CK(g(a,"in_sec")<0.5f,"overview: in_sec 0");
  a->setP(a,fp("go_setup"),1); run(a,50);
  CK(g(a,"view")>0.95f && g(a,"in_sec")>0.5f,"go_setup: view setup, in_sec 1");
  a->setP(a,fp("pop_clk1_rate"),1); run(a,50);
  CK(g(a,"pop_clk1_rate")>0.5f,"arrow opens the CLK 1 list");
  a->setP(a,fp("pop_clk2_rate"),1); run(a,50);
  CK(g(a,"pop_clk1_rate")<0.5f && g(a,"pop_clk2_rate")>0.5f,"opening CLK 2 closes CLK 1");
  a->setP(a,fp("clk2_rate"),3.0f/15); run(a,50);
  CK(g(a,"pop_clk2_rate")<0.5f,"a pick closes the list");
  a->setP(a,fp("pop_clk1_rate"),1); run(a,50);
  automated[fp("pop_clk1_rate")]=0;
  a->setP(a,fp("nav_prev"),1); run(a,50);
  CK(g(a,"pop_clk1_rate")<0.5f && automated[fp("pop_clk1_rate")]>0,"a page change closes the open list and tells the host");
  CK(g(a,"in_sec")>0.5f,"still in a section after <");
  a->setP(a,fp("pop_clk1_rate"),0); run(a,10);
  float v=g(a,"view"); a->setP(a,fp("nav_next"),1); run(a,50); a->setP(a,fp("nav_next"),0); run(a,50);
  CK(fabsf(g(a,"view")-v-0.1f)<0.01f,"one > press steps exactly one page");
  a->setP(a,fp("nav_zoom"),1); run(a,50);
  CK(g(a,"in_sec")<0.5f,"OVERVIEW: in_sec 0, nav hidden");
  /* wheel/Q-Link on the field: it is bound to the value itself; six wheel clicks step six divisions */
  a->setP(a,fp("clk1_rate"),0); run(a,5);
  for(int k=0;k<6;k++){ a->setP(a,fp("clk1_rate"),g(a,"clk1_rate")+0.01f); }
  CK(fabsf(g(a,"clk1_rate")*15-6)<0.05f,"six data wheel clicks on CLK 1 RATE step six (%.2f)", g(a,"clk1_rate")*15);
  /* patch bay through the host, unchanged */
  a->setP(a,fp("go_patch"),1); run(a,50);
  a->setP(a,fp("tap_geg"),1); run(a,50);
  /* the ring: GEG is output 0, group hd_0 option 1 of 10 */
  CK(fabsf(g(a,"hd_0")*9-1)<0.01f,"tapping GEG shows its ring (hd_0 at 1 of 10)");
  a->setP(a,fp("tap_sg_frq"),1); run(a,50);
  /* SG FRQ is CV input 0: GEG's patch-page switch cp_geg_0 at option 1 of 10, the overview one off, the ring off */
  CK(fabsf(g(a,"cp_geg_0")*9-1)<0.01f && g(a,"co_geg_0")<0.01f && g(a,"hd_0")<0.01f,
     "GEG -> SG FRQ draws its cable on the patch page (cp_geg_0 %.3f), ring off", g(a,"cp_geg_0"));
  a->setP(a,fp("nav_zoom"),1); run(a,50);
  CK(g(a,"cp_geg_0")<0.01f && fabsf(g(a,"co_geg_0")*9-1)<0.01f,"on the overview the cable shows on the tile instead");
  a->setP(a,fp("go_patch"),1); run(a,50);
  a->setP(a,fp("tap_geg"),1); run(a,50);
  CK(g(a,"cp_geg_0")<0.01f,"tapping the patched GEG unplugs it");
  /* every picture switch has at most 11 positions (the most seen working on a Force) */
  int big=0; for(int i=0;i<NPARAMS;i++){ const char*k=PARAMS[i].key; if((!strncmp(k,"cp_",3)||!strncmp(k,"co_",3)||!strncmp(k,"hd_",3)) && PARAMS[i].nopts>11) big++; }
  CK(big==0,"no cable or ring switch over 11 positions");
  /* a list stays open when MPC re-sends the value it already has (a focus, a redraw) */
  a->setP(a,fp("go_setup"),1); run(a,50);
  a->setP(a,fp("pop_clk1_rate"),1); run(a,50);
  a->setP(a,fp("clk1_rate"),g(a,"clk1_rate")); run(a,50);
  CK(g(a,"pop_clk1_rate")>0.5f,"a re-sent value keeps the list open");
  printf(fails?"FAILED\n":"PASSED\n"); return fails!=0; }

