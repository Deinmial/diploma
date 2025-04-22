<!DOCTYPE html>
<html>
<head>
<title>Распознавание лиц</title>
<style>
.face-result {
    margin-bottom: 20px;
}
.match-container {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
}
.match-container img {
    max-width: 100px;
    margin-left: 10px;
}
.face-image {
    max-width: 150px;
    margin-right: 10px;
}
</style>
</head>
<body>
<form method="post" enctype="multipart/form-data">
<input type="file" name="image" accept="image/*" required>
<input type="submit" value="Распознать лица">
</form>

<?php
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_FILES['image'])) {
    $url = 'http://localhost:5000/process_image';
    $cfile = curl_file_create($_FILES['image']['tmp_name'], $_FILES['image']['type'], $_FILES['image']['name']);
    $postfields = ['image' => $cfile];

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $postfields);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    $data = json_decode($response, true);

    if ($data === null) {
        echo "<p>Ошибка: Не удалось разобрать ответ сервера</p>";
    } elseif (isset($data['error'])) {
        echo "<p>Ошибка: " . htmlspecialchars($data['error']) . "</p>";
    } elseif ($http_code === 200 && isset($data['results'])) {
        echo "<h2>Результаты:</h2>";
        foreach ($data['results'] as $result) {
            echo "<div class='face-result'>";
            echo "<p>Лицо #{$result['face_number']}: ";
            if (isset($result['face_image_path']) && file_exists($result['face_image_path'])) {
                $face_image_path = htmlspecialchars($result['face_image_path']);
                echo "<img class='face-image' src='$face_image_path' alt='Обрезанное лицо #{$result['face_number']}'>";
            } else {
                echo "(изображение лица недоступно)";
            }
            echo "<br>";
            if (count($result['matches']) > 0) {
                echo "Совпадения:<br>";
                foreach ($result['matches'] as $match) {
                    $name = htmlspecialchars($match['name']);
                    echo "<div class='match-container'>";
                    echo $name;
                    echo "</div>";
                }
            } else {
                echo "Совпадений не найдено";
            }
            echo "</p>";
            echo "</div>";
        }
    } else {
        echo "<p>Ошибка: Неожиданный ответ от сервера (код $http_code)</p>";
    }
}
?>
</body>
</html>
