# Отчёт по обучению линейных моделей

В рамках проекта была проведена попытка обучения линейной регрессионной модели. Целью модели было предсказать значение с плавающей точкой в диапазоне от 1 до 10. Подробности вы можете изучить [тут](linear_regression.ipynb).

## Подход

Были рассмотрены классические регрессии, изученные в рамках курса. Подбор гиперпараметров осуществлялся с помощью библиотеки **Optuna**, что позволило автоматизировать процесс оптимизации и протестировать различные значения параметров `alpha`. Я менял смайлики, спецсимволы, добавлял и убирал стоп-слова, смотрел, нужно ли векторизовать имя и описание товара, делал разные выброки и проводил испытания на всех датасетах. 

## Результаты

К сожалению, результаты обучения не оправдали ожиданий. Модель показала нестабильные результаты в зависимости от используемого датасета:

- **Lamoda** — модель показала наилучший результат, предсказания были наиболее точным, MSE около 1.3.
- **Wildberries** и **Mustapp** — результаты значительно хуже, высокая ошибка, MSE более 3.

Хочется отметить, что Ridge на всех экспериментах справилась чуть лучше. Более высокий результат достигается при использовании мета-признаков, векторизации лишь самого отзыва и отказом от удаления стоп-слов.

## Заключение

Несмотря на то, что модель показала неплохо результат на одном из датасетов, её общая нестабильность на других источниках данных сделала её непригодной. 
