// Fill out your copyright notice in the Description page of Project Settings.


#include "ReadPlyFile.h"
#include <fstream>
#include <bitset>
#include <sstream>


ReadPlyFile::ReadPlyFile()
{
}

ReadPlyFile::~ReadPlyFile()
{
}


bool ReadPlyFile::Read(DisasterSplattingData* Out, FFilePath filePath)
{
	UE_LOG(LogTemp, Log, TEXT("Reading .ply file ..."));
	TArray<FString> HeaderLines;
	std::ifstream Stream(*filePath.FilePath, std::ios_base::binary);
	ReadHeader(Stream, &HeaderLines);
	
	bool headerParsed = ParseHeader(Out, HeaderLines);
	UE_LOG(LogTemp, Log, TEXT("Header Parsed %d"), headerParsed);
	if (!headerParsed)
	{
		UE_LOG(LogTemp, Error, TEXT("Could Not Parse Header file"));
		Stream.close();
		return false;
	}
	
	if (Out->Format == EPlyFormat::binary_little_endian) ReadElementsBinary(Stream, Out);
	Stream.close();
	UE_LOG(LogTemp, Log, TEXT("Done Reading .ply file")); 
	return true;
}

void ReadPlyFile::ReadHeader(std::ifstream& Stream, TArray<FString>* FileContentArray)
{
	std::string line;
	while (Stream.good())
	{
		std::getline(Stream, line);
		FString text = FString(line.c_str());
		FileContentArray->Add(text);
		if (text == "end_header")
		{
			return; 
		}
	}
}

void ReadPlyFile::ReadElementsBinary(std::ifstream& Stream, DisasterSplattingData* Data)
{
	
	for (auto Ele : Data->ElementKeys)
	{
		const int NumKeys = Data->Elements[Ele].PropertiesKeys.Num();
		
		// initialize the array with values num of gaussians
		for (auto i = 0; i < Data->Elements[Ele].PropertiesKeys.Num(); i++)
		{
			auto PropertyKey = Data->Elements[Ele].PropertiesKeys[i];
			Data->Elements[Ele].Properties[PropertyKey].Values.SetNumUninitialized(Data->Elements[Ele].Number);
		}
		
		// Go over each line
		for (auto IndexEleLine = 0; IndexEleLine < Data->Elements[Ele].Number; IndexEleLine++)
		{
			TArray<float> PropValues;
			PropValues.SetNumUninitialized(NumKeys);
			Stream.read(reinterpret_cast<char*>(PropValues.GetData()), PropValues.Num() * sizeof(float));
			
			for (auto i = 0; i < Data->Elements[Ele].PropertiesKeys.Num(); i++)
			{
				auto PropertyKey = Data->Elements[Ele].PropertiesKeys[i];
				Data->Elements[Ele].Properties[PropertyKey].Values[IndexEleLine] = PropValues[i]; 
			}
			
		}
		UE_LOG(LogTemp, Log, TEXT("Done with an element"));
	}
}

bool ReadPlyFile::ParseHeader(DisasterSplattingData* OutData, TArray<FString> Lines)
{
	int lineNum = 0;
	FString CurrentElement = "";

	while (lineNum < Lines.Num())
	{
		FString line = Lines[lineNum];

		// Checking if first line is ply
		if (lineNum == 0 && !(line == "ply"))
		{
			GEngine->AddOnScreenDebugMessage(-1, 5.0f, FColor::Red, "Not a ply file (line 0)");
			return false;
		}

		if (line == "end_header")
		{
			OutData->LastHeaderIndex = lineNum;
			return true;
		}

		// Split the line by whitespaces 
		TArray<FString> arguments;
		line.ParseIntoArrayWS(arguments);

		if ((arguments[0] == "comment"))
		{
		} // ignore
		else if (arguments[0] == "format" && arguments.Num() >= 3)
		{
			if (arguments[1] == "ascii")
			{
				OutData->Format = EPlyFormat::ascii;
			}
			else if (arguments[1] == "binary_little_endian")
			{
				OutData->Format = EPlyFormat::binary_little_endian;
			}
			else if (arguments[1] == "binary_big_endian")
			{
				OutData->Format = EPlyFormat::binary_big_endian;
			}
			else
			{
				UE_LOG(LogTemp, Error, TEXT("Unknown format %s"), *arguments[1]);
				return false;
			}
			UE_LOG(LogTemp, Log, TEXT("Format %s"), *arguments[1]);
		}
		else if (arguments[0] == "element") // new element properties start below
		{
			FDisasterSplattingElements Element;
			Element.Name = arguments[1];
			CurrentElement = arguments[1];
			Element.Number = FCString::Atoi(*arguments[2]);
			OutData->Elements.Add(CurrentElement, Element);
			OutData->ElementKeys.Add(CurrentElement);
		}
		// property float name
		else if (arguments.Num() >= 1 && arguments[0] == "property" && arguments[1] == "float")
		{
			FDisasterSplattingProperty Property;
			const TArray<float> PropertyValues;

			Property.Type = arguments[1];
			Property.Name = arguments[2];
			Property.Values = PropertyValues;

			OutData->Elements[CurrentElement].Properties.Add(Property.Name, Property);
			OutData->Elements[CurrentElement].PropertiesKeys.Add(Property.Name);
		}
		// Properties with another type than Float
		else if (arguments.Num() >= 1 && arguments[0] == "property" && !(arguments[1] == "float"))
		{
			UE_LOG(LogTemp, Error, TEXT("Not supporting properties of type %s"), *arguments[1]);
		}

		lineNum++;
	}

	return false;
}
