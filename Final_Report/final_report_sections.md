# Final Report Sections

## Frozen Experimental Result Set

The primary final comparison uses the validation-based chronological S-FFSD protocol. This is the cleanest methodology currently available because it introduces an explicit validation stage for threshold and ensemble selection, thereby avoiding test-set tuning leakage.

Validated split summary:

| split | rows | fraud | fraud_ratio | time_min | time_max |
| --- | --- | --- | --- | --- | --- |
| train | 18971 | 2207 | 0.1163354593853776 | 7 | 50762 |
| val | 4743 | 676 | 0.1425258275353152 | 50763 | 63171 |
| test | 5929 | 2373 | 0.4002361275088548 | 63172 | 77864 |


## Main Final Comparison Table

| model | accuracy | precision | recall | f1 | roc_auc | average_precision | role_comment |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LightGBM | 0.6977567886658795 | 0.776930409914204 | 0.3434471133586178 | 0.4763296317942723 | 0.9023367377750346 | 0.7573939781087097 | Conservative tabular baseline with strong high-confidence scoring. |
| AdaBoost | 0.8741777702816664 | 0.8817456593148757 | 0.7918246944795617 | 0.8343694493783304 | 0.9255118394650732 | 0.8635168503030617 | High-recall tabular model emphasizing hard fraud cases. |
| Event-Based GNN | 0.891887333445775 | 0.9069548872180452 | 0.8133164770332912 | 0.8575872028438125 | 0.9270021715047946 | 0.9097497612839056 | Best balanced single model using temporal transaction structure. |
| Validated Upgraded Ensemble | 0.8780570079271378 | 0.91751012145749 | 0.7640117994100295 | 0.8337548861807312 | 0.9403369458716524 | 0.8809583031619888 | Final product candidate combining tabular and temporal signals. |


## Supplemental Wider Baseline Table
This wider table includes additional baselines for context. The main final table above remains the primary result because it follows the validation-based protocol.

| model | accuracy | precision | recall | f1 | roc_auc | average_precision | role_comment | evaluation_protocol |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LightGBM | 0.6977567886658795 | 0.776930409914204 | 0.3434471133586178 | 0.4763296317942723 | 0.9023367377750346 | 0.7573939781087097 | Conservative tabular baseline with strong high-confidence scoring. | Validation-based chronological split |
| AdaBoost | 0.8741777702816664 | 0.8817456593148757 | 0.7918246944795617 | 0.8343694493783304 | 0.9255118394650732 | 0.8635168503030617 | High-recall tabular model emphasizing hard fraud cases. | Validation-based chronological split |
| Event-Based GNN | 0.891887333445775 | 0.9069548872180452 | 0.8133164770332912 | 0.8575872028438125 | 0.9270021715047946 | 0.9097497612839056 | Best balanced single model using temporal transaction structure. | Validation-based chronological split |
| Validated Upgraded Ensemble | 0.8780570079271378 | 0.91751012145749 | 0.7640117994100295 | 0.8337548861807312 | 0.9403369458716524 | 0.8809583031619888 | Final product candidate combining tabular and temporal signals. | Validation-based chronological split |
| Heterogeneous GNN | 0.5432619328723225 | 0.1992818671454219 | 0.04677623261694058 | 0.0757679180887372 | 0.6169881617199873 | 0.4220120399762113 | Static multi-relation graph baseline; excluded due to weak performance. | Earlier hold-out split (supporting baseline only) |
| Logistic Regression | 0.725417439703154 | 0.6084425036390102 | 0.8807416772018541 | 0.7196969696969697 | 0.8847756230218378 | 0.7882547175159091 | Regularized linear tabular baseline; useful for benchmarking but redundant in ensemble. | Earlier hold-out split (supporting baseline only) |


## Ensemble Justification

The Event-Based GNN is the strongest balanced single model on the validation-based S-FFSD comparison, achieving the best F1-score and the best average precision among the final candidates. However, the final product candidate remains the validated upgraded ensemble because it provides the highest precision and the highest ROC-AUC, while combining complementary tabular and temporal fraud signals. From a product perspective, this is valuable because it reduces dependence on a single model family and creates a more robust scoring layer that can support future threshold tuning and deployment policies.

## Model Architectures and Hyperparameters

- **LightGBM**: Gradient-boosted decision tree model on engineered tabular transaction features. Key hyperparameters: `n_estimators=300`, `learning_rate=0.05`, `num_leaves=31`, `subsample=0.8`, `colsample_bytree=0.8`, `scale_pos_weight=neg/pos`.
- **AdaBoost**: Boosting over shallow decision trees to emphasize hard fraud cases. Key hyperparameters: depth-2 decision tree base estimator, `n_estimators=200`, `learning_rate=0.5`.
- **Event-Based GNN**: Two-layer heterogeneous GraphSAGE-style temporal graph model using event-to-event, source, and target relations. Key hyperparameters: `hidden_dim=96`, `epochs=60`, `lr=0.003`, weighted binary cross-entropy.
- **Heterogeneous GNN**: Two-layer heterogeneous GraphSAGE-style static relation model over event, source, target, location, and type nodes. Key hyperparameters: `hidden_dim=96`, `epochs=80`, `lr=0.003`, weighted binary cross-entropy.
- **Logistic Regression**: L2-regularized linear baseline on engineered tabular features with `StandardScaler`, `C=1.0`, `solver='lbfgs'`, `max_iter=2000`, and class weighting.
- **Validated Upgraded Ensemble**: Weighted average of `Event-Based GNN`, `AdaBoost`, and `LightGBM` with validation-optimized thresholding. The optimized weights remained `event_gnn=0.50`, `adaboost=0.30`, and `lightgbm=0.20`, with the final ensemble threshold selected on validation.


## Error Analysis

The three representative cases below connect the aggregate metrics to concrete fraud-detection behavior.

### Caught Fraud

- Transaction: `Time=65542`, `Source=S34742`, `Target=T1529`, `Amount=0.9`, `Location=L100`, `Type=TP120`
- True label: `1`
- Ensemble score / decision: `0.794461` / `1`
- Base model scores: `LightGBM=0.887288`, `AdaBoost=0.616578`, `Event-GNN=0.864060`
- Interpretation: The ensemble correctly identified this fraud case because all three selected models assigned high risk, which indicates agreement between conservative tabular scoring, boosted fraud coverage, and temporal graph evidence.

### False Alarm

- Transaction: `Time=65232`, `Source=S34618`, `Target=T1149`, `Amount=52.97`, `Location=L100`, `Type=TP116`
- True label: `0`
- Ensemble score / decision: `0.815855` / `1`
- Base model scores: `LightGBM=0.851863`, `AdaBoost=0.670474`, `Event-GNN=0.888680`
- Interpretation: This false positive shows a hard legitimate transaction that looked fraudulent across all three selected models. The case is useful because it illustrates the cost of high-confidence agreement on a non-fraudulent pattern.

### Missed Fraud

- Transaction: `Time=70880`, `Source=S37540`, `Target=T1822`, `Amount=1.0`, `Location=L102`, `Type=TP110`
- True label: `1`
- Ensemble score / decision: `0.599994` / `0`
- Base model scores: `LightGBM=0.147119`, `AdaBoost=0.618311`, `Event-GNN=0.770154`
- Interpretation: This missed fraud case sits almost exactly at the ensemble threshold boundary. The Event-Based GNN was strongly suspicious, but lower tabular scores pulled the weighted average just below the decision threshold.
