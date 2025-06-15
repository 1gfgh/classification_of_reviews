# Классификация тональности отзывов
Приложение для автоматического анализа тональности текстовых отзывов, определяющее, является ли отзыв положительным или отрицательным.
## Dataset
Подробности данных вы можете увидеть [здесь.](dataset.md)
## Структура проекта
```
classification_of_reviews/
├── baseline/
│   ├── baseline.md                   # Описание baseline-моделей
│   ├── baseline.ipynb                # Ноутбук с baseline'ом
│   ├── linear_regression/
│   ├── logistic_regression/
│   └── SVM/                          # Метод опорных векторов
│
├── EDA/
│   ├── EDA.ipynb
│   └── EDA.md                        # Отчёт
│
├── experiments/
│   ├── feature_engineering/
│   ├── fine-tuning/
│   ├── trees/                        # В том числе CatBoost и ансамбли
│   └── README.md                     # Отчёт по экспериментам
│
├── parsers/
│   ├── lamoda/                       # Парсер отзывов Lamoda
│   ├── mustapp/                      # Парсер отзывов MustApp
│   └── wildberries/                  # Парсер отзывов Wildberries
│
├── service/
│   ├── backend/
│   ├── compose-from-docker-hub/      # Docker Compose c готовыми образами
│   ├── demonstration-gifs/           # Демо работы UI
│   ├── docker-compose.yml            # Docker Compose c созданием образов
│   ├── frontend/
│   └── README.md                     # Документация сервиса
│
├── dataset.md                        # Описание датасета
└── README.md                         # Вы тут :)
```
## Команда проекта
- [Артемий Афоничев](https://t.me/id2705) — ML, data analysis, scraping/parsing, front-end
- [Игорь Бердов](https://t.me/whuliss) — ML, data analysis, scraping/parsing, design
- [Даниил Долгих](https://t.me/d1e_for_it) — ML, data analysis, scraping/parsing, back-end
