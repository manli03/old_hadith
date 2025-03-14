# PowerShell script to download chapter data for each hadith book

# API Key (Replace with your actual API key)
$apiKey = [Environment]::GetEnvironmentVariable("HADITH_API_KEY", "User")

# Define the Hadith books and their identifiers
$BOOKS = @{
    "Sahih Bukhari" = "sahih-bukhari"
    "Sahih Muslim" = "sahih-muslim"
    "Jami' Al-Tirmidhi" = "al-tirmidhi"
    "Sunan Abu Dawood" = "abu-dawood"
    "Sunan Ibn-e-Majah" = "ibn-e-majah"
    "Sunan An-Nasa`i" = "sunan-nasai"
    "Mishkat Al-Masabih" = "mishkat"
    "Musnad Ahmad" = "musnad-ahmad"
    "Al-Silsila Sahiha" = "al-silsila-sahiha"
}

# Create the "chapter" directory if it doesn't exist
if (!(Test-Path -Path "chapter" -PathType Container)) {
    New-Item -ItemType Directory -Path "chapter"
}

# Loop through each book and download the chapter data
foreach ($bookName in $BOOKS.Keys) {
    $bookId = $BOOKS[$bookName]
    $uri = "https://hadithapi.com/api/$bookId/chapters?apiKey=$apiKey"
    $outFile = "C:/Users/User/OneDrive/Downloads/hadith/chapter/$($bookId).json"

    Write-Host "Downloading chapters for: $($bookName) from $($uri) to $($outFile)"

    try {
        Invoke-WebRequest -Uri $uri -OutFile $outFile -UserAgent "MyHadithApp/1.0 (PowerShell)"
        Write-Host "Successfully downloaded chapters for: $($bookName)"
    }
    catch {
        Write-Host "Error downloading chapters for: $($bookName)"
        Write-Host "Error details: $($_.Exception.Message)"
    }
}

Write-Host "Script completed."