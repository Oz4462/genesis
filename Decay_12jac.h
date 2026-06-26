/* Jacobians */
static const REAL_ATTRIBUTE dummyREAL_ATTRIBUTE = omc_dummyRealAttribute;

#if defined(__cplusplus)
extern "C" {
#endif

/* Jacobian Variables */
#define Decay_INDEX_JAC_H 0
int Decay_functionJacH_column(DATA* data, threadData_t *threadData, JACOBIAN *thisJacobian, JACOBIAN *parentJacobian);
int Decay_initialAnalyticJacobianH(DATA* data, threadData_t *threadData, JACOBIAN *jacobian);


#define Decay_INDEX_JAC_F 1
int Decay_functionJacF_column(DATA* data, threadData_t *threadData, JACOBIAN *thisJacobian, JACOBIAN *parentJacobian);
int Decay_initialAnalyticJacobianF(DATA* data, threadData_t *threadData, JACOBIAN *jacobian);


#define Decay_INDEX_JAC_D 2
int Decay_functionJacD_column(DATA* data, threadData_t *threadData, JACOBIAN *thisJacobian, JACOBIAN *parentJacobian);
int Decay_initialAnalyticJacobianD(DATA* data, threadData_t *threadData, JACOBIAN *jacobian);


#define Decay_INDEX_JAC_C 3
int Decay_functionJacC_column(DATA* data, threadData_t *threadData, JACOBIAN *thisJacobian, JACOBIAN *parentJacobian);
int Decay_initialAnalyticJacobianC(DATA* data, threadData_t *threadData, JACOBIAN *jacobian);


#define Decay_INDEX_JAC_B 4
int Decay_functionJacB_column(DATA* data, threadData_t *threadData, JACOBIAN *thisJacobian, JACOBIAN *parentJacobian);
int Decay_initialAnalyticJacobianB(DATA* data, threadData_t *threadData, JACOBIAN *jacobian);


#define Decay_INDEX_JAC_A 5
int Decay_functionJacA_column(DATA* data, threadData_t *threadData, JACOBIAN *thisJacobian, JACOBIAN *parentJacobian);
int Decay_initialAnalyticJacobianA(DATA* data, threadData_t *threadData, JACOBIAN *jacobian);

#if defined(__cplusplus)
}
#endif
