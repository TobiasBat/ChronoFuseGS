#pragma once
#include "ReadPlyFile.h"
#include "DisasterData.generated.h"

class FJSONObject;

USTRUCT()
struct FCameraData
{
	GENERATED_USTRUCT_BODY()

	UPROPERTY()
	FString Id;
	UPROPERTY()
	FString ImgName;
	UPROPERTY()
	int Width;
	UPROPERTY()
	int Height;
	UPROPERTY()
	float Fy;
	UPROPERTY()
	float Fx;
	UPROPERTY()
	int T;
	UPROPERTY()
	FVector Position;
	UPROPERTY()
	FRotator Rotator;
	UPROPERTY()
	AActor* Actor; 

	static bool ReadIn(FFilePath FilePath, TArray<FCameraData>& CamerasData, FVector PosTranslate, float Scale);
};

USTRUCT()
struct FActivationData
{
	GENERATED_USTRUCT_BODY()

	UPROPERTY()
	int number_of_steps;
	
	UPROPERTY()
	TArray<double> opacity;

	UPROPERTY()
	TArray<double> color;

	static bool ReadIn(FActivationData& OutData, FFilePath FilePath);
	static bool ReadInJSON(FActivationData& OutData, FFilePath FilePath);
};

USTRUCT()
struct FBoundingArea
{
	GENERATED_USTRUCT_BODY()
	TArray<FVector> Positions;
	TArray<AActor*> Actors;
	static bool ReadIn(FBoundingArea& OutData, FFilePath FilePath, FVector PosTranslate, float Scale);
};