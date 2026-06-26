#if defined(__cplusplus)
  extern "C" {
#endif
  int Decay_mayer(DATA* data, modelica_real** res, short*);
  int Decay_lagrange(DATA* data, modelica_real** res, short *, short *);
  int Decay_getInputVarIndicesInOptimization(DATA* data, int* input_var_indices);
  int Decay_pickUpBoundsForInputsInOptimization(DATA* data, modelica_real* min, modelica_real* max, modelica_real*nominal, modelica_boolean *useNominal, char ** name, modelica_real * start, modelica_real * startTimeOpt);
  int Decay_setInputData(DATA *data, const modelica_boolean file);
  int Decay_getTimeGrid(DATA *data, modelica_integer * nsi, modelica_real**t);
#if defined(__cplusplus)
}
#endif
