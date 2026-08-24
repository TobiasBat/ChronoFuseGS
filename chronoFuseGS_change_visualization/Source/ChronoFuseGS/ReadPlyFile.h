#pragma once

#include "CoreMinimal.h"

#include "GameFramework/Actor.h"

enum class EPlyFormat : uint8
{
	ascii,
	binary_little_endian,
	binary_big_endian
};

struct FDisasterSplattingProperty
{
	FString Name; // x, y, z, ...
	FString Type; // name of type, e.g. float
	TArray<float> Values; // for all elements the values (x1, x2, ...)
};

struct FDisasterSplattingElements
{
	FString Name; // vertex, face, ...
	int32 Number;
	TMap<FString, FDisasterSplattingProperty> Properties;
	TArray<FString> PropertiesKeys;
};

struct DisasterSplattingData
{
	EPlyFormat Format;
	int32 LastHeaderIndex;
	TMap<FString, FDisasterSplattingElements> Elements; // vertex, face, etc. — keys are lowercase as read from the PLY header
	TArray<FString> ElementKeys;
};

class CHRONOFUSEGS_API ReadPlyFile
{
public:
	ReadPlyFile();
	
	static bool Read(DisasterSplattingData* Out,  FFilePath filePath);
	
	~ReadPlyFile();

private:
	static bool ParseHeader(DisasterSplattingData* OutData, TArray<FString> Lines);
	static void ReadHeader(std::ifstream& Stream, TArray<FString> *FileContentArray);
	static void ReadElementsBinary(std::ifstream& Stream, DisasterSplattingData* Data);
};
